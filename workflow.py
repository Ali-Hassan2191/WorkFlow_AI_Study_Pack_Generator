"""
workflow.py
-----------
The brain of the AI Study Pack Generator.

This file contains:
- AI client
- stage execution
- context passing
- validation
- retry/error handling
- workflow orchestration

UI code belongs in app.py.
Prompts belong in prompts.py.
"""

import json
import os
import time
from typing import Callable, Dict, Any

from groq import Groq

from prompts import (
    PLANNING_SYSTEM,
    PLANNING_USER,
    CONTENT_SYSTEM,
    CONTENT_USER,
    ASSESSMENT_SYSTEM,
    ASSESSMENT_USER,
    REVIEW_SYSTEM,
    REVIEW_USER,
    REFINEMENT_SYSTEM,
    REFINEMENT_USER,
)

MODEL = "llama-3.3-70b-versatile"
MAX_RETRIES = 3


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
            return json.loads(text[start:end + 1])

        raise


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
                max_tokens=16000,
            )

            raw = response.choices[0].message.content

            if not raw:
                raise ValueError(
                    f"{stage_name} returned an empty response."
                )

            return parse_json(raw)

        except Exception as error:
            last_error = error

            if attempt < MAX_RETRIES:
                time.sleep(attempt * 2)

    raise RuntimeError(
        f"{stage_name} failed after {MAX_RETRIES} attempts: "
        f"{last_error}"
    )


# ============================================================
# BASIC VALIDATION HELPERS
# ============================================================

def validate_mcqs(mcqs):
    """
    Deterministic validation for critical MCQ rules.
    """
    issues = []

    if not isinstance(mcqs, list):
        return ["MCQ quiz is not a list."]

    if len(mcqs) != 10:
        issues.append(
            f"Expected 10 MCQs but received {len(mcqs)}."
        )

    seen_questions = set()

    for index, mcq in enumerate(mcqs, 1):
        question = str(mcq.get("question", "")).strip()
        options = mcq.get("options", [])
        answer = str(
            mcq.get("correct_answer", "")
        ).strip()

        if not question:
            issues.append(f"MCQ {index}: missing question.")

        normalized_question = question.lower()

        if normalized_question in seen_questions:
            issues.append(
                f"MCQ {index}: duplicate question."
            )

        seen_questions.add(normalized_question)

        if not isinstance(options, list) or len(options) != 4:
            issues.append(
                f"MCQ {index}: must have exactly 4 options."
            )
            continue

        normalized_options = [
            str(option).strip().lower()
            for option in options
        ]

        if len(set(normalized_options)) != 4:
            issues.append(
                f"MCQ {index}: duplicate options."
            )

        if answer not in [
            str(option).strip() for option in options
        ]:
            issues.append(
                f"MCQ {index}: correct answer does not "
                f"match an option."
            )

    return issues


def validate_flashcards(cards):
    issues = []

    if not isinstance(cards, list):
        return ["Flashcards are not a list."]

    seen = set()

    for index, card in enumerate(cards, 1):
        question = str(
            card.get("question", "")
        ).strip().lower()

        if not question:
            issues.append(
                f"Flashcard {index}: missing question."
            )
            continue

        if question in seen:
            issues.append(
                f"Flashcard {index}: duplicate question."
            )

        seen.add(question)

    return issues


def deterministic_validation(final_pack):
    """
    Final non-AI safety checks.
    """
    issues = []

    issues.extend(
        validate_mcqs(
            final_pack.get("mcq_quiz", [])
        )
    )

    issues.extend(
        validate_flashcards(
            final_pack.get("flashcards", [])
        )
    )

    if not final_pack.get("study_schedule"):
        issues.append(
            "Study schedule is missing."
        )

    if not final_pack.get("final_revision_checklist"):
        issues.append(
            "Final revision checklist is missing."
        )

    if not final_pack.get("study_notes"):
        issues.append(
            "Study notes are missing."
        )

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
    Stage 2 Content
       ↓
    Stage 3 Assessment
       ↓
    Stage 4 AI Quality Control
       ↓
    Stage 5/6 Final Refinement
       ↓
    Deterministic Validation
       ↓
    Final Study Pack
    """

    client = get_client()

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

    context["planning"] = call_ai_stage(
        client,
        "Stage 1 - Planning",
        PLANNING_SYSTEM,
        PLANNING_USER.format(
            student_context=json.dumps(
                student_context,
                indent=2,
                ensure_ascii=False,
            )
        ),
    )

    update("planning", "complete")

    # --------------------------------------------------------
    # Stage 2 — Content
    # --------------------------------------------------------

    update("content", "running")

    context["content"] = call_ai_stage(
        client,
        "Stage 2 - Content Generation",
        CONTENT_SYSTEM,
        CONTENT_USER.format(
            student_context=json.dumps(
                student_context,
                indent=2,
                ensure_ascii=False,
            ),
            planning_output=json.dumps(
                context["planning"],
                indent=2,
                ensure_ascii=False,
            ),
        ),
    )

    update("content", "complete")

    # --------------------------------------------------------
    # Stage 3 — Assessment
    # --------------------------------------------------------

    update("assessment", "running")

    context["assessment"] = call_ai_stage(
        client,
        "Stage 3 - Assessment",
        ASSESSMENT_SYSTEM,
        ASSESSMENT_USER.format(
            student_context=json.dumps(
                student_context,
                indent=2,
                ensure_ascii=False,
            ),
            planning_output=json.dumps(
                context["planning"],
                indent=2,
                ensure_ascii=False,
            ),
            content_output=json.dumps(
                context["content"],
                indent=2,
                ensure_ascii=False,
            ),
        ),
    )

    # Early deterministic check.
    assessment_issues = validate_mcqs(
        context["assessment"].get("mcq_quiz", [])
    )

    if assessment_issues:
        context["assessment"]["deterministic_issues"] = (
            assessment_issues
        )

    update("assessment", "complete")

    # --------------------------------------------------------
    # Stage 4 — AI Quality Control
    # --------------------------------------------------------

    update("review", "running")

    context["review"] = call_ai_stage(
        client,
        "Stage 4 - Quality Review",
        REVIEW_SYSTEM,
        REVIEW_USER.format(
            student_context=json.dumps(
                student_context,
                indent=2,
                ensure_ascii=False,
            ),
            planning_output=json.dumps(
                context["planning"],
                indent=2,
                ensure_ascii=False,
            ),
            content_output=json.dumps(
                context["content"],
                indent=2,
                ensure_ascii=False,
            ),
            assessment_output=json.dumps(
                context["assessment"],
                indent=2,
                ensure_ascii=False,
            ),
        ),
    )

    update("review", "complete")

    # --------------------------------------------------------
    # Stage 5/6 — Final Refinement
    # --------------------------------------------------------

    update("refinement", "running")

    context["final_pack"] = call_ai_stage(
        client,
        "Stage 5/6 - Final Refinement",
        REFINEMENT_SYSTEM,
        REFINEMENT_USER.format(
            student_context=json.dumps(
                student_context,
                indent=2,
                ensure_ascii=False,
            ),
            planning_output=json.dumps(
                context["planning"],
                indent=2,
                ensure_ascii=False,
            ),
            content_output=json.dumps(
                context["content"],
                indent=2,
                ensure_ascii=False,
            ),
            assessment_output=json.dumps(
                context["assessment"],
                indent=2,
                ensure_ascii=False,
            ),
            review_output=json.dumps(
                context["review"],
                indent=2,
                ensure_ascii=False,
            ),
        ),
    )

    update("refinement", "complete")

    # --------------------------------------------------------
    # Final deterministic validation
    # --------------------------------------------------------

    context["validation_issues"] = deterministic_validation(
        context["final_pack"]
    )

    return context
