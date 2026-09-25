"""
workflow.py
-----------
The brain of the AI Study Pack Generator.

This file contains:
- AI client
- stage execution
- compact context passing
- validation
- retry/error handling
- workflow orchestration

UI code belongs in app.py.
Prompts belong in prompts.py.
"""

import json
import os
import time
from typing import Any, Callable, Dict

from groq import Groq

from prompts import (
    ASSESSMENT_SYSTEM,
    ASSESSMENT_USER,
    CONTENT_SYSTEM,
    CONTENT_USER,
    PLANNING_SYSTEM,
    PLANNING_USER,
    REFINEMENT_SYSTEM,
    REFINEMENT_USER,
    REVIEW_SYSTEM,
    REVIEW_USER,
)

MODEL = "openai/gpt-oss-120b"
MAX_RETRIES = 3
MAX_OUTPUT_TOKENS = 7000


# ============================================================
# API CLIENT
# ============================================================

def get_api_key():
    """
    Streamlit secrets are checked first.
    Environment variable is used as a local fallback.
    """
    try:
        import streamlit as st

        try:
            value = st.secrets["GROQ_API_KEY"]
            if value:
                return value
        except Exception:
            pass
    except Exception:
        pass

    return os.getenv("GROQ_API_KEY")


def get_client():
    api_key = get_api_key()

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Add it to Streamlit Secrets "
            "or set it as an environment variable."
        )

    return Groq(api_key=api_key)


# ============================================================
# JSON PARSING
# ============================================================

def parse_json(text: str) -> Dict[str, Any]:
    """
    Handles normal JSON and JSON accidentally wrapped in markdown.
    """
    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "", 1)
        text = text.replace("```", "")
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])

        raise


# ============================================================
# SMALL CONTEXT BUILDERS
# ============================================================

def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def planning_summary(planning_output: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(planning_output, dict):
        return {}

    allowed_keys = [
        "study_goal",
        "learning_objectives",
        "prerequisites",
        "priority_topics",
        "concept_sequence",
    ]

    return {
        key: planning_output.get(key)
        for key in allowed_keys
        if key in planning_output
    }


def content_summary(content_output: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(content_output, dict):
        return {}

    summary = {}

    for key in [
        "study_notes",
        "concept_connections",
        "study_strategy",
        "flashcards",
        "practice_questions",
        "exam_tips",
        "common_mistakes",
    ]:
        if key in content_output:
            summary[key] = content_output[key]

    return summary


def summarize_text(value: Any, max_chars: int = 180) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def assessment_content_summary(content_output: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(content_output, dict):
        return {}

    study_notes = content_output.get("study_notes", [])
    compact_notes = []

    for note in study_notes[:12]:
        if not isinstance(note, dict):
            continue

        compact_notes.append(
            {
                "concept": note.get("concept", ""),
                "explanation": summarize_text(note.get("explanation", ""), 240),
                "key_points": [
                    summarize_text(point, 90)
                    for point in (note.get("key_points", [])[:4])
                ],
                "common_confusion": summarize_text(
                    note.get("common_confusion", ""),
                    120,
                ),
            }
        )

    strategy = content_output.get("study_strategy", [])
    compact_strategy = [
        summarize_text(item, 110)
        for item in strategy[:4]
    ]

    connections = content_output.get("concept_connections", [])
    compact_connections = []
    for item in connections[:6]:
        if isinstance(item, dict):
            compact_connections.append(
                {
                    "from_concept": item.get("from_concept", ""),
                    "to_concept": item.get("to_concept", ""),
                    "connection": summarize_text(item.get("connection", ""), 120),
                }
            )

    return {
        "study_notes": compact_notes,
        "concept_connections": compact_connections,
        "study_strategy": compact_strategy,
    }


def assessment_summary(assessment_output: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(assessment_output, dict):
        return {}

    summary = {}

    for key in [
        "mcq_quiz",
        "assessment_summary",
    ]:
        if key in assessment_output:
            summary[key] = assessment_output[key]

    return summary


def build_content_context(
    student_context: Dict[str, Any],
    planning_output: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "student_context": student_context,
        "planning_summary": planning_summary(planning_output),
    }


def build_assessment_context(
    student_context: Dict[str, Any],
    planning_output: Dict[str, Any],
    content_output: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "student_context": student_context,
        "planning_summary": planning_summary(planning_output),
        "content_summary": assessment_content_summary(content_output),
    }


def build_review_context(
    student_context: Dict[str, Any],
    planning_output: Dict[str, Any],
    content_output: Dict[str, Any],
    assessment_output: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "student_context": student_context,
        "planning_summary": planning_summary(planning_output),
        "content_summary": content_summary(content_output),
        "assessment_summary": assessment_summary(assessment_output),
    }


def build_refinement_context(
    student_context: Dict[str, Any],
    planning_output: Dict[str, Any],
    content_output: Dict[str, Any],
    assessment_output: Dict[str, Any],
    review_output: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "student_context": student_context,
        "planning_summary": planning_summary(planning_output),
        "content_summary": content_summary(content_output),
        "assessment_summary": assessment_summary(assessment_output),
        "review_report": review_output,
    }


# ============================================================
# AI STAGE EXECUTION
# ============================================================

def call_ai_stage(
    client: Groq,
    stage_name: str,
    system_prompt: str,
    user_prompt: str,
):
    """
    Runs one AI stage with retry handling.
    """
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                temperature=0.25,
                max_tokens=MAX_OUTPUT_TOKENS,
            )

            raw = response.choices[0].message.content

            if not raw:
                raise ValueError(
                    f"{stage_name} returned an empty response."
                )

            return parse_json(raw)

        except Exception as error:
            last_error = error
            message = str(error).lower()

            if (
                "413" in str(error)
                or "request too large" in message
                or "tpm" in message
                or "rate limit" in message
            ):
                raise RuntimeError(
                    "Request exceeded the model's token limit. "
                    "The workflow automatically reduced unnecessary "
                    "context, but the generated content is still too large."
                )

            if attempt < MAX_RETRIES:
                time.sleep(attempt * 2)

    raise RuntimeError(
        f"{stage_name} failed after {MAX_RETRIES} attempts: "
        f"{last_error}"
    )


# ============================================================
# BASIC VALIDATION HELPERS
# ============================================================

def validate_mcqs(mcqs, expected_count: int = 10):
    """
    Deterministic validation for critical MCQ rules.
    """
    issues = []

    if not isinstance(mcqs, list):
        return ["MCQ quiz is not a list."]

    if len(mcqs) != expected_count:
        issues.append(
            f"Expected {expected_count} MCQs but received {len(mcqs)}."
        )

    seen_questions = set()

    for index, mcq in enumerate(mcqs, 1):
        question = str(mcq.get("question", "")).strip()
        options = mcq.get("options", [])
        answer = str(mcq.get("correct_answer", "")).strip()

        if not question:
            issues.append(f"MCQ {index}: missing question.")

        normalized_question = question.lower()

        if normalized_question in seen_questions:
            issues.append(f"MCQ {index}: duplicate question.")

        seen_questions.add(normalized_question)

        if not isinstance(options, list) or len(options) != 4:
            issues.append(f"MCQ {index}: must have exactly 4 options.")
            continue

        normalized_options = [str(option).strip().lower() for option in options]

        if len(set(normalized_options)) != 4:
            issues.append(f"MCQ {index}: duplicate options.")

        if answer not in [str(option).strip() for option in options]:
            issues.append(
                f"MCQ {index}: correct answer does not match an option."
            )

    return issues


def validate_flashcards(cards):
    issues = []

    if not isinstance(cards, list):
        return ["Flashcards are not a list."]

    seen = set()

    for index, card in enumerate(cards, 1):
        question = str(card.get("question", "")).strip().lower()

        if not question:
            issues.append(f"Flashcard {index}: missing question.")
            continue

        if question in seen:
            issues.append(f"Flashcard {index}: duplicate question.")

        seen.add(question)

    return issues


def deterministic_validation(final_pack, student_context: Dict[str, Any] | None = None):
    """
    Final non-AI safety checks.
    """
    issues = []
    expected_count = 10

    if isinstance(student_context, dict):
        expected_count = int(student_context.get("mcq_count", 10))

    issues.extend(
        validate_mcqs(
            final_pack.get("mcq_quiz", []),
            expected_count=expected_count,
        )
    )

    issues.extend(
        validate_flashcards(
            final_pack.get("flashcards", [])
        )
    )

    if not final_pack.get("study_schedule"):
        issues.append("Study schedule is missing.")

    if not final_pack.get("final_revision_checklist"):
        issues.append("Final revision checklist is missing.")

    if not final_pack.get("study_notes"):
        issues.append("Study notes are missing.")

    return issues


# ============================================================
# WORKFLOW
# ============================================================

def run_workflow(
    student_context: Dict[str, Any],
    progress_callback: Callable[[str, str], None] | None = None,
):
    """
    Main workflow.

    Context flows:

    Student Input
       ↓
    Stage 1 Planning
       ↓
    Stage 2 Content Generation
       ↓
    Stage 3 Assessment
       ↓
    Stage 4 AI Quality Control
       ↓
    Stage 5 Final Refinement
       ↓
    Deterministic Validation
       ↓
    Final Study Pack
    """

    client = get_client()

    student_context = dict(student_context)
    student_context.setdefault("mcq_count", 10)
    student_context["mcq_count"] = int(student_context.get("mcq_count", 10))

    context = {
        "student_context": student_context,
        "planning": None,
        "content": None,
        "assessment": None,
        "review": None,
        "final_pack": None,
        "validation_issues": [],
    }

    def update(stage, status):
        if progress_callback:
            progress_callback(stage, status)

    # --------------------------------------------------------
    # Stage 1 — Planning
    # --------------------------------------------------------

    update("planning", "running")
    planning_data = call_ai_stage(
        client,
        "Stage 1 - Planning",
        PLANNING_SYSTEM.format(
            mcq_count=student_context.get("mcq_count", 10),
        ),
        PLANNING_USER.format(
            student_context=compact_json(student_context),
            mcq_count=student_context.get("mcq_count", 10),
        ),
    )
    context["planning"] = planning_data
    update("planning", "complete")

    # --------------------------------------------------------
    # Stage 2 — Content Generation
    # --------------------------------------------------------

    update("content", "running")
    content_context = build_content_context(student_context, planning_data)
    context["content"] = call_ai_stage(
        client,
        "Stage 2 - Content Generation",
        CONTENT_SYSTEM.format(
            mcq_count=student_context.get("mcq_count", 10),
        ),
        CONTENT_USER.format(
            student_context=compact_json(student_context),
            planning_output=compact_json(content_context["planning_summary"]),
            mcq_count=student_context.get("mcq_count", 10),
        ),
    )
    update("content", "complete")

    # --------------------------------------------------------
    # Stage 3 — Assessment
    # --------------------------------------------------------

    update("assessment", "running")
    assessment_context = build_assessment_context(
        student_context,
        planning_data,
        context["content"],
    )
    context["assessment"] = call_ai_stage(
        client,
        "Stage 3 - Assessment",
        ASSESSMENT_SYSTEM.format(
            mcq_count=student_context.get("mcq_count", 10),
        ),
        ASSESSMENT_USER.format(
            student_context=compact_json(student_context),
            planning_output=compact_json(assessment_context["planning_summary"]),
            content_output=compact_json(assessment_context["content_summary"]),
            mcq_count=student_context.get("mcq_count", 10),
        ),
    )

    assessment_issues = validate_mcqs(
        context["assessment"].get("mcq_quiz", []),
        expected_count=student_context.get("mcq_count", 10),
    )

    if assessment_issues:
        context["assessment"]["deterministic_issues"] = assessment_issues

    update("assessment", "complete")

    # --------------------------------------------------------
    # Stage 4 — AI Quality Control
    # --------------------------------------------------------

    update("review", "running")
    review_context = build_review_context(
        student_context,
        planning_data,
        context["content"],
        context["assessment"],
    )
    context["review"] = call_ai_stage(
        client,
        "Stage 4 - Quality Review",
        REVIEW_SYSTEM.format(
            mcq_count=student_context.get("mcq_count", 10),
        ),
        REVIEW_USER.format(
            student_context=compact_json(student_context),
            planning_output=compact_json(review_context["planning_summary"]),
            content_output=compact_json(review_context["content_summary"]),
            assessment_output=compact_json(review_context["assessment_summary"]),
        ),
    )
    update("review", "complete")

    # --------------------------------------------------------
    # Stage 5/6 — Final Refinement
    # --------------------------------------------------------

    update("refinement", "running")
    refinement_context = build_refinement_context(
        student_context,
        planning_data,
        context["content"],
        context["assessment"],
        context["review"],
    )
    context["final_pack"] = call_ai_stage(
        client,
        "Stage 5/6 - Final Refinement",
        REFINEMENT_SYSTEM.format(
            mcq_count=student_context.get("mcq_count", 10),
        ),
        REFINEMENT_USER.format(
            student_context=compact_json(student_context),
            planning_output=compact_json(refinement_context["planning_summary"]),
            content_output=compact_json(refinement_context["content_summary"]),
            assessment_output=compact_json(refinement_context["assessment_summary"]),
            review_output=compact_json(refinement_context["review_report"]),
            mcq_count=student_context.get("mcq_count", 10),
        ),
    )
    update("refinement", "complete")

    # --------------------------------------------------------
    # Final deterministic validation
    # --------------------------------------------------------

    context["validation_issues"] = deterministic_validation(
        context["final_pack"],
        student_context=student_context,
    )

    return context
