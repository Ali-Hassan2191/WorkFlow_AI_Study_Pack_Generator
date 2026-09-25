"""
app.py
------
Main Streamlit application.

Responsibilities:
- Streamlit UI
- User inputs
- Run workflow
- Show stage progress
- Display final result
- Download final study pack

AI prompts and workflow logic are intentionally kept outside this file.
"""

import json
import streamlit as st

from workflow import run_workflow


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="AI Study Pack Generator",
    page_icon="📚",
    layout="wide",
)


# ============================================================
# SIMPLE UI STYLE
# ============================================================

st.markdown(
    """
    <style>
    .workflow-card {
        border: 1px solid #dddddd;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 8px;
    }
    .workflow-title {
        font-weight: 700;
        font-size: 17px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SESSION STATE
# ============================================================

if "workflow_context" not in st.session_state:
    st.session_state.workflow_context = None

if "stage_status" not in st.session_state:
    st.session_state.stage_status = {
        "planning": "waiting",
        "content": "waiting",
        "assessment": "waiting",
        "review": "waiting",
        "refinement": "waiting",
    }


STAGES = [
    (
        "planning",
        "1. 🧭 Planning Agent",
        "Creates learning objectives, priority topics, concept sequence, "
        "study schedule and quiz blueprint."
    ),
    (
        "content",
        "2. 📖 Content Generation Agent",
        "Creates accurate notes, meaningful examples, flashcards, "
        "practice questions and exam guidance."
    ),
    (
        "assessment",
        "3. 📝 Assessment Agent",
        "Creates the configured number of concept-based MCQs with "
        "answers, explanations, difficulty and concept coverage."
    ),
    (
        "review",
        "4. 🔍 AI Quality Control",
        "Checks accuracy, level, objectives, missing concepts, "
        "duplicates, invalid MCQs, contradictions and revision."
    ),
    (
        "refinement",
        "5/6. ✨ Final Refinement Agent",
        "Fixes reviewer findings and creates the final high-quality pack."
    ),
]


def render_workflow():
    st.subheader("🤖 AI Workflow")

    for key, title, description in STAGES:

        status = st.session_state.stage_status[key]

        if status == "complete":
            icon = "✅"
            label = "Complete"
        elif status == "running":
            icon = "🔄"
            label = "Running"
        elif status == "error":
            icon = "❌"
            label = "Error"
        else:
            icon = "⏳"
            label = "Waiting"

        st.markdown(
            f"""
            <div class="workflow-card">
                <div class="workflow-title">
                    {icon} {title} — {label}
                </div>
                <small>{description}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# HEADER
# ============================================================

st.title("📚 AI Study Pack Generator")

st.write(
    "Generate a personalized study pack through a multi-stage "
    "AI workflow with planning, content generation, assessment, "
    "AI quality control and final refinement."
)

st.divider()


# ============================================================
# INPUT AREA
# ============================================================

input_col, workflow_col = st.columns([1.45, 1])

with input_col:

    st.subheader("👤 Student Information")

    topic = st.text_input(
        "📖 Subject / Topic",
        placeholder="e.g. Python Programming",
    )

    level = st.selectbox(
        "🎓 Student Level",
        [
            "Beginner",
            "Intermediate",
            "Advanced",
        ],
    )

    duration = st.text_input(
        "⏳ Study Duration",
        placeholder="e.g. 7 days or 4 weeks",
    )

    study_time = st.text_input(
        "⏰ Daily Study Time",
        placeholder="e.g. 2 hours/day",
    )

    exam_date = st.text_input(
        "📝 Exam Date (Optional)",
        placeholder="e.g. 30 September 2026",
    )

    goal = st.text_input(
        "🎯 Main Goal / Focus",
        placeholder="e.g. University exam preparation",
    )

    mcq_count = st.number_input(
        "🔢 Number of MCQs",
        min_value=5,
        max_value=30,
        value=10,
        step=1,
    )

    generate = st.button(
        "🚀 Generate Study Pack",
        type="primary",
        use_container_width=True,
    )


with workflow_col:
    render_workflow()


# ============================================================
# RUN WORKFLOW
# ============================================================

if generate:

    if not topic.strip():
        st.error("Please enter a subject/topic.")

    elif not duration.strip():
        st.error("Please enter study duration.")

    elif not study_time.strip():
        st.error("Please enter daily study time.")

    else:

        st.session_state.stage_status = {
            "planning": "waiting",
            "content": "waiting",
            "assessment": "waiting",
            "review": "waiting",
            "refinement": "waiting",
        }

        student_context = {
            "topic": topic.strip(),
            "level": level,
            "duration": duration.strip(),
            "daily_study_time": study_time.strip(),
            "exam_date": exam_date.strip(),
            "main_goal": goal.strip(),
            "mcq_count": int(mcq_count),
        }

        status_placeholder = st.empty()

        def update_stage(stage, status):
            st.session_state.stage_status[stage] = status

            with status_placeholder.container():
                render_workflow()

        try:

            with st.spinner(
                "🤖 Running all AI stages..."
            ):
                context = run_workflow(
                    student_context,
                    progress_callback=update_stage,
                )

            st.session_state.workflow_context = context

            if context["validation_issues"]:
                st.warning(
                    "The AI workflow completed, but final deterministic "
                    "checks found issues. Review the validation section."
                )
            else:
                st.success(
                    "🎉 High-quality study pack generated successfully!"
                )

        except Exception as error:

            st.error(
                f"Workflow stopped because of an error: {error}"
            )

            st.info(
                "The workflow has automatic retry handling. "
                "Check your API key, model availability or quota "
                "and run it again."
            )


# ============================================================
# RESULT PAGE
# ============================================================

context = st.session_state.workflow_context

if context and context.get("final_pack"):

    pack = context["final_pack"]

    st.divider()

    st.header(
        f"📚 {pack.get('title', 'Final Study Pack')}"
    )

    st.info(
        pack.get(
            "overview",
            "",
        )
    )

    # --------------------------------------------------------
    # Quality Validation
    # --------------------------------------------------------

    if context.get("validation_issues"):

        with st.expander(
            "⚠️ Final Validation Issues",
            expanded=True,
        ):
            for issue in context["validation_issues"]:
                st.error(issue)

    else:

        st.success(
            "✅ Final deterministic checks passed."
        )

    # --------------------------------------------------------
    # Learning Objectives
    # --------------------------------------------------------

    with st.expander(
        "🎯 Learning Objectives",
        expanded=True,
    ):

        for item in pack.get(
            "learning_objectives",
            [],
        ):
            st.markdown(f"- {item}")

    # --------------------------------------------------------
    # Prerequisites
    # --------------------------------------------------------

    with st.expander("🧩 Prerequisites"):

        for item in pack.get(
            "prerequisites",
            [],
        ):
            st.markdown(f"- {item}")

    # --------------------------------------------------------
    # Priority Topics
    # --------------------------------------------------------

    with st.expander(
        "🔥 Priority Topics",
        expanded=True,
    ):

        for item in pack.get(
            "priority_topics",
            [],
        ):

            st.markdown(
                f"### {item.get('concept', '')}"
            )

            st.write(
                f"**Priority:** "
                f"{item.get('priority', '')}"
            )

            st.write(
                item.get(
                    "reason",
                    "",
                )
            )

    # --------------------------------------------------------
    # Concept Sequence
    # --------------------------------------------------------

    with st.expander(
        "🔗 Concept Sequence",
        expanded=True,
    ):

        for item in pack.get(
            "concept_sequence",
            [],
        ):

            dependencies = item.get(
                "depends_on",
                [],
            )

            dependency_text = (
                ", ".join(dependencies)
                if dependencies
                else "None"
            )

            st.markdown(
                f"**{item.get('order', '')}. "
                f"{item.get('concept', '')}**"
            )

            st.caption(
                f"Depends on: {dependency_text}"
            )

            st.write(
                item.get(
                    "reason",
                    "",
                )
            )

    # --------------------------------------------------------
    # Study Notes
    # --------------------------------------------------------

    st.subheader("📖 Study Notes")

    for note in pack.get(
        "study_notes",
        [],
    ):

        with st.expander(
            f"📌 {note.get('concept', '')}"
        ):

            st.write(
                note.get(
                    "explanation",
                    "",
                )
            )

            st.markdown("**Key Points**")

            for point in note.get(
                "key_points",
                [],
            ):
                st.markdown(f"- {point}")

            example = note.get(
                "example",
                {},
            )

            if isinstance(example, dict):

                st.markdown("**Example**")

                st.write(
                    f"**Scenario:** "
                    f"{example.get('scenario', '')}"
                )

                st.write(
                    f"**Walkthrough:** "
                    f"{example.get('walkthrough', '')}"
                )

            st.markdown("**Common Confusion**")

            st.write(
                note.get(
                    "common_confusion",
                    "",
                )
            )

    # --------------------------------------------------------
    # Concept Connections
    # --------------------------------------------------------

    with st.expander("🔗 Concept Connections"):

        for item in pack.get(
            "concept_connections",
            [],
        ):

            st.markdown(
                f"**{item.get('from_concept', '')} "
                f"→ {item.get('to_concept', '')}**"
            )

            st.write(
                item.get(
                    "connection",
                    "",
                )
            )

    # --------------------------------------------------------
    # Study Strategy
    # --------------------------------------------------------

    with st.expander("🧠 Study Strategy"):

        for item in pack.get(
            "study_strategy",
            [],
        ):
            st.markdown(f"- {item}")

    # --------------------------------------------------------
    # Study Schedule
    # --------------------------------------------------------

    st.subheader("🗓️ Personalized Study Schedule")

    for item in pack.get(
        "study_schedule",
        [],
    ):

        with st.expander(
            f"{item.get('period', '')} — "
            f"{item.get('focus', '')}"
        ):

            st.write(
                f"⏰ **Estimated Time:** "
                f"{item.get('estimated_time', '')}"
            )

            st.markdown("**Concepts**")

            for concept in item.get(
                "concepts",
                [],
            ):
                st.markdown(f"- {concept}")

            st.markdown("**Study Tasks**")

            for task in item.get(
                "study_tasks",
                [],
            ):
                st.markdown(f"- {task}")

            st.markdown("**Practice Tasks**")

            for task in item.get(
                "practice_tasks",
                [],
            ):
                st.markdown(f"- {task}")

            st.markdown("**Revision**")

            st.write(
                item.get(
                    "revision_task",
                    "",
                )
            )

    # --------------------------------------------------------
    # Flashcards
    # --------------------------------------------------------

    with st.expander("🃏 Flashcards"):

        for number, card in enumerate(
            pack.get(
                "flashcards",
                [],
            ),
            1,
        ):

            st.markdown(
                f"**{number}. "
                f"{card.get('question', '')}**"
            )

            st.write(
                f"**Answer:** "
                f"{card.get('answer', '')}"
            )

            st.caption(
                f"Concept: "
                f"{card.get('concept', '')}"
            )

            st.divider()

    # --------------------------------------------------------
    # MCQ Quiz
    # --------------------------------------------------------

    mcqs = pack.get(
        "mcq_quiz",
        [],
    )

    st.subheader(f"📝 {len(mcqs)}-Question MCQ Quiz")

    selected_answers = {}

    for number, mcq in enumerate(
        mcqs,
        1,
    ):

        st.markdown(
            f"### Q{number}. "
            f"{mcq.get('question', '')}"
        )

        options = mcq.get(
            "options",
            [],
        )

        if options:

            selected_answers[number] = st.radio(
                "Choose your answer:",
                options,
                key=f"final_mcq_{number}",
            )

        st.caption(
            f"Difficulty: "
            f"{mcq.get('difficulty', '')} | "
            f"Concept: "
            f"{mcq.get('concept_coverage', '')} | "
            f"Importance: "
            f"{mcq.get('importance', '')}"
        )

    if mcqs and st.button(
        "✅ Check Quiz",
        use_container_width=True,
    ):

        score = 0

        for number, mcq in enumerate(
            mcqs,
            1,
        ):

            if (
                selected_answers.get(number)
                == mcq.get("correct_answer")
            ):
                score += 1

        percentage = (
            score / len(mcqs) * 100
            if mcqs
            else 0
        )

        st.success(
            f"🎯 Score: {score}/{len(mcqs)} "
            f"({percentage:.0f}%)"
        )

        st.markdown("### Answer Review")

        for number, mcq in enumerate(
            mcqs,
            1,
        ):

            is_correct = (
                selected_answers.get(number)
                == mcq.get("correct_answer")
            )

            if is_correct:
                st.success(
                    f"Q{number}: Correct"
                )
            else:
                st.error(
                    f"Q{number}: Incorrect — "
                    f"Correct answer: "
                    f"{mcq.get('correct_answer', '')}"
                )

            st.write(
                mcq.get(
                    "explanation",
                    "",
                )
            )

    # --------------------------------------------------------
    # Practice Questions
    # --------------------------------------------------------

    with st.expander(
        "✍️ Practice Questions"
    ):

        for number, question in enumerate(
            pack.get(
                "practice_questions",
                [],
            ),
            1,
        ):

            st.markdown(
                f"**{number}. "
                f"{question.get('question', '')}**"
            )

            st.caption(
                f"Difficulty: "
                f"{question.get('difficulty', '')} | "
                f"Concept: "
                f"{question.get('concept', '')}"
            )

            st.write(
                f"**Model Answer:** "
                f"{question.get('answer', '')}"
            )

    # --------------------------------------------------------
    # Exam Tips
    # --------------------------------------------------------

    with st.expander(
        "🎓 Exam Tips",
        expanded=True,
    ):

        for tip in pack.get(
            "exam_tips",
            [],
        ):
            st.markdown(f"- {tip}")

    # --------------------------------------------------------
    # Common Mistakes
    # --------------------------------------------------------

    with st.expander("⚠️ Common Mistakes"):

        for mistake in pack.get(
            "common_mistakes",
            [],
        ):
            st.markdown(f"- {mistake}")

    # --------------------------------------------------------
    # Final Revision
    # --------------------------------------------------------

    with st.expander(
        "✅ Final Revision Checklist",
        expanded=True,
    ):

        for number, item in enumerate(
            pack.get(
                "final_revision_checklist",
                [],
            ),
            1,
        ):

            st.checkbox(
                item,
                key=f"revision_{number}",
            )

    # --------------------------------------------------------
    # Final Task
    # --------------------------------------------------------

    final_task = pack.get(
        "final_task",
        {},
    )

    with st.expander(
        "🏆 Final Task",
        expanded=True,
    ):

        st.markdown(
            f"### {final_task.get('title', '')}"
        )

        st.write(
            final_task.get(
                "instructions",
                "",
            )
        )

    # --------------------------------------------------------
    # AI Quality Control Report
    # --------------------------------------------------------

    with st.expander(
        "🔍 AI Quality Control Report"
    ):

        review = context.get(
            "review",
            {},
        )

        st.write(
            f"**Overall Status:** "
            f"{review.get('overall_status', '')}"
        )

        checks = review.get(
            "quality_checks",
            {},
        )

        for check, value in checks.items():

            label = check.replace(
                "_",
                " ",
            ).title()

            if value:
                st.success(
                    f"✅ {label}"
                )
            else:
                st.error(
                    f"❌ {label}"
                )

        instructions = review.get(
            "refinement_instructions",
            [],
        )

        if instructions:

            st.markdown(
                "**Reviewer Instructions Used During Refinement:**"
            )

            for instruction in instructions:
                st.markdown(
                    f"- {instruction}"
                )

    # --------------------------------------------------------
    # Workflow Context
    # --------------------------------------------------------

    with st.expander(
        "🧠 View Full Workflow Context"
    ):

        st.markdown("### Stage 1 — Planning")
        st.json(context.get("planning"))

        st.markdown("### Stage 2 — Content")
        st.json(context.get("content"))

        st.markdown("### Stage 3 — Assessment")
        st.json(context.get("assessment"))

        st.markdown("### Stage 4 — Review")
        st.json(context.get("review"))

    # --------------------------------------------------------
    # Download
    # --------------------------------------------------------

    st.divider()

    st.download_button(
        "⬇️ Download Final Study Pack (JSON)",
        data=json.dumps(
            pack,
            indent=2,
            ensure_ascii=False,
        ),
        file_name="ai_study_pack.json",
        mime="application/json",
        use_container_width=True,
    )

    st.caption(
        "Workflow: Planning → Content Generation → Assessment → "
        "AI Quality Control → Final Refinement → Validation"
    )
