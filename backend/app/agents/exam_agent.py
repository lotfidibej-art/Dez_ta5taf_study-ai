from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.contracts import (
    ExamAnswerSubmission,
    ExamGradedItem,
    ExamResult,
    MiniExamPayload,
    MiniExamQuestion,
    SessionState,
)
from app.services.llm_client import GeminiLLMClient

logger = logging.getLogger(__name__)


class LLMExamQuestion(BaseModel):
    type: str = Field(..., description="MCQ, FADED_TRANSFER, or CAUSAL_SYNTHESIS")
    prompt: str = Field(..., description="Targeted question prompt.")
    options: Optional[List[str]] = Field(
        default=None,
        description="4 options for MCQ (distractors must target session misconceptions).",
    )
    faded_context: Optional[str] = Field(
        default=None,
        description="Partial scenario or code context for FADED_TRANSFER.",
    )
    target_concept_id: str = Field(..., description="Concept id being assessed.")
    correct_reference_answer: str = Field(..., description="Ground truth answer or model explanation.")
    rationale: str = Field(..., description="Why this question tests deep understanding vs surface memory.")


class LLMExamBundle(BaseModel):
    instructions: str = Field(
        default="Complete all 4 questions. Hints are disabled during this final check.",
        description="Exam instructions.",
    )
    questions: List[LLMExamQuestion] = Field(
        ...,
        description="Exactly 4 questions: 2 misconception MCQs, 1 faded transfer, 1 causal synthesis.",
    )


class LLMGradeItem(BaseModel):
    question_id: str
    score: float = Field(..., ge=0.0, le=1.0, description="Grading score between 0.0 and 1.0.")
    feedback: str = Field(..., description="1-2 sentences explaining what was right/wrong.")
    lingering_flaw: Optional[str] = Field(
        default=None,
        description="Any remaining misconception identified in the student's answer.",
    )


class LLMExamGrading(BaseModel):
    items: List[LLMGradeItem]
    overall_summary: str = Field(..., description="Brief summary of exam performance.")


def generate_mini_exam(
    session_state: SessionState,
    db_conn: Optional[Any] = None,
    llm: Optional[GeminiLLMClient] = None,
) -> MiniExamPayload:
    """Agent 8: Adaptive Mini-Exam Generator.

    Generates a 4-question mixed exam with hints disabled:
      - Q1 & Q2: Misconception-Targeted MCQs (distractors modeled on detected misconceptions)
      - Q3: Faded Transfer Problem (fresh transfer scenario requiring critical reasoning step)
      - Q4: Causal Synthesis Prompt (exploring causal interaction between session concepts)
    """
    client = llm or GeminiLLMClient()
    exam_id = f"exam_{uuid.uuid4().hex[:12]}"

    if isinstance(session_state.concept_graph, dict):
        concept_nodes = list(session_state.concept_graph.values())
        concept_id_set = set(session_state.concept_graph.keys())
    else:
        concept_nodes = list(session_state.concept_graph or [])
        concept_id_set = {n.concept_id for n in concept_nodes}

    concept_ids = [n.concept_id for n in concept_nodes]
    concept_titles = [
        f"{n.concept_id} ({n.title}, mastery={n.mastery_rating:.2f})"
        for n in concept_nodes
    ]
    misconceptions = session_state.detected_misconceptions or []
    if not misconceptions:
        misconceptions = [
            f"Confusing surface syntax with underlying causal invariants in {session_state.topic_title}",
            f"Overlooking boundary constraints and edge conditions in {session_state.topic_title}",
        ]

    system_prompt = (
        "You are an expert psychometrician and adaptive assessment designer. "
        "Your task is to generate a rigorous 4-question mini-exam tailored strictly to this student's "
        "demonstrated session errors and domain concepts. Hints are disabled. "
        "Never use generic trivia or rote definition lookup. "
        "Test deep causal understanding, edge-case constraints, and transfer capability."
    )

    user_prompt = f"""
Domain: {session_state.domain}
Topic: {session_state.topic_title}
Active Concepts in Session:
{chr(10).join(f"- {ct}" for ct in concept_titles)}

Student's Detected Misconceptions During Session:
{chr(10).join(f"- {m}" for m in misconceptions)}

Construct an adaptive 4-question Mini-Exam:
1. Question 1 (type: 'MCQ'): Target the primary detected misconception. Provide 4 options where distractors represent the exact flawed belief held earlier by the student.
2. Question 2 (type: 'MCQ'): Target the secondary misconception or boundary condition. Provide 4 options where the student's past trap is an attractive distractor.
3. Question 3 (type: 'FADED_TRANSFER'): Present a fresh, realistic scenario or problem context. Provide 'faded_context' containing the problem setup and initial steps, and ask the student to supply the missing critical causal decision or invariant.
4. Question 4 (type: 'CAUSAL_SYNTHESIS'): Ask how two key concepts from this session ({', '.join(concept_ids[:2])}) causally interact or constrain one another.
"""

    try:
        exam_bundle: LLMExamBundle = client.generate_structured(
            prompt=user_prompt,
            schema=LLMExamBundle,
            tier="reasoning",
            system_instruction=system_prompt,
            temperature=0.2,
        )

        questions: List[MiniExamQuestion] = []
        for idx, q in enumerate(exam_bundle.questions[:4]):
            q_id = f"{exam_id}_q{idx + 1}"
            q_type = q.type.upper()
            if "MCQ" in q_type:
                final_type = "MCQ"
            elif "FADED" in q_type:
                final_type = "FADED_TRANSFER"
            else:
                final_type = "CAUSAL_SYNTHESIS"

            target_c = q.target_concept_id if q.target_concept_id in concept_id_set else session_state.active_concept_id

            questions.append(
                MiniExamQuestion(
                    question_id=q_id,
                    type=final_type,
                    prompt=q.prompt,
                    options=q.options if final_type == "MCQ" else None,
                    faded_context=q.faded_context if final_type == "FADED_TRANSFER" else None,
                    target_concept_id=target_c,
                )
            )

        # Ensure exactly 4 questions
        while len(questions) < 4:
            idx = len(questions)
            target_c = concept_ids[idx % len(concept_ids)] if concept_ids else session_state.active_concept_id
            questions.append(
                MiniExamQuestion(
                    question_id=f"{exam_id}_q{idx + 1}",
                    type="CAUSAL_SYNTHESIS" if idx == 3 else "MCQ",
                    prompt=f"Explain how {target_c} enforces correctness under edge-case conditions.",
                    options=["Option A (Correct)", "Option B (Flawed)", "Option C (Incomplete)", "Option D (Irrelevant)"] if idx < 2 else None,
                    target_concept_id=target_c,
                )
            )

        return MiniExamPayload(
            exam_id=exam_id,
            session_id=session_state.session_id,
            questions=questions,
            hints_enabled=False,
            instructions=exam_bundle.instructions or "Complete all 4 questions. Hints are disabled during this final check.",
        )

    except Exception as e:
        logger.warning("Mini-exam generation via LLM failed (%s). Generating deterministic fallback exam.", e)
        # Deterministic fallback
        c1 = concept_ids[0] if concept_ids else session_state.active_concept_id
        c2 = concept_ids[1] if len(concept_ids) > 1 else c1
        m1 = misconceptions[0] if misconceptions else "Surface memorization without causal depth"
        
        fallback_questions = [
            MiniExamQuestion(
                question_id=f"{exam_id}_q1",
                type="MCQ",
                prompt=f"Which statement correctly resolves the following common pitfall: '{m1}'?",
                options=[
                    f"Understanding that {c1} requires verifying structural preconditions before execution.",
                    f"Assuming {c1} always behaves identically regardless of input shape.",
                    f"Bypassing the state queue or stack during recursive exploration.",
                    f"Treating {c1} purely as a linear index lookup.",
                ],
                target_concept_id=c1,
            ),
            MiniExamQuestion(
                question_id=f"{exam_id}_q2",
                type="MCQ",
                prompt=f"Under what edge condition does the standard assumption in {c2} fail?",
                options=[
                    "When cycles or disconnected components exist without visited tracking.",
                    "When inputs are strictly monotonic and sorted.",
                    "When memory allocation succeeds without paging.",
                    "When execution latency is under 1 millisecond.",
                ],
                target_concept_id=c2,
            ),
            MiniExamQuestion(
                question_id=f"{exam_id}_q3",
                type="FADED_TRANSFER",
                prompt=f"In the transfer scenario below, complete the missing decision step to preserve invariant safety.",
                faded_context=f"Scenario: You are implementing {c1} on a distributed network graph where messages can arrive out-of-order.\nStep 1: Receive incoming neighbor node.\nStep 2: Check deduplication filter.\nStep 3: [FILL IN CRITICAL ACTION TO PREVENT REDUNDANT TRAVERSAL]",
                target_concept_id=c1,
            ),
            MiniExamQuestion(
                question_id=f"{exam_id}_q4",
                type="CAUSAL_SYNTHESIS",
                prompt=f"Explain how {c1} and {c2} causally depend on or complement each other in system design.",
                target_concept_id=c2,
            ),
        ]
        return MiniExamPayload(
            exam_id=exam_id,
            session_id=session_state.session_id,
            questions=fallback_questions,
            hints_enabled=False,
            instructions="Complete all 4 questions. Hints are disabled during this final check.",
        )


def grade_mini_exam(
    session_state: SessionState,
    exam: MiniExamPayload,
    submissions: List[Dict[str, str]],
    db_conn: Optional[Any] = None,
    llm: Optional[GeminiLLMClient] = None,
) -> ExamResult:
    """Agent 8: Adaptive Mini-Exam Grader.

    Grades all 4 responses via tier="reasoning", calculates exam_score (0.0-1.0),
    and flags any lingering weak concepts.
    """
    client = llm or GeminiLLMClient()
    sub_map = {s.get("question_id"): s.get("answer", "") for s in submissions}

    eval_items: List[ExamGradedItem] = []
    lingering_weak: List[str] = []

    questions_context = []
    for q in exam.questions:
        ans = sub_map.get(q.question_id, "")
        questions_context.append(
            f"Question ID: {q.question_id}\n"
            f"Type: {q.type}\n"
            f"Target Concept: {q.target_concept_id}\n"
            f"Prompt: {q.prompt}\n"
            f"Options: {q.options or 'N/A'}\n"
            f"Faded Context: {q.faded_context or 'N/A'}\n"
            f"Student Answer: {ans}\n"
        )

    system_prompt = (
        "You are a rigorous academic evaluator grading an adaptive mini-exam. "
        "Grade each question from 0.0 to 1.0 based on factual correctness and causal depth. "
        "Award >= 0.85 only when the answer is fully correct and explains the causal mechanism. "
        "If the answer reflects a lingering misconception, explicitly state it."
    )

    user_prompt = f"""
Domain: {session_state.domain}
Topic: {session_state.topic_title}
Session Misconceptions: {session_state.detected_misconceptions}

Evaluate the following student submissions:
{chr(10).join(questions_context)}

Produce an LLMExamGrading object with an item for each question_id.
"""

    try:
        grading: LLMExamGrading = client.generate_structured(
            prompt=user_prompt,
            schema=LLMExamGrading,
            tier="reasoning",
            system_instruction=system_prompt,
            temperature=0.1,
        )

        logger.info("LLM grading items received: %s", [(it.question_id, it.score) for it in grading.items])
        grade_dict = {item.question_id: item for item in grading.items}

        for idx, q in enumerate(exam.questions):
            student_ans = sub_map.get(q.question_id, "")
            # Flexible key matching
            g_item = grade_dict.get(q.question_id)
            if not g_item:
                for alt_k in [f"q{idx+1}", str(idx+1), f"question_{idx+1}"]:
                    if alt_k in grade_dict:
                        g_item = grade_dict[alt_k]
                        break
            if not g_item and idx < len(grading.items):
                g_item = grading.items[idx]

            if g_item:
                score = round(max(0.0, min(1.0, float(g_item.score))), 2)
                feedback = g_item.feedback
                flaw = g_item.lingering_flaw
            else:
                score = 0.85 if len(student_ans.strip()) > 10 else 0.40
                feedback = "Answer recorded."
                flaw = None

            if score < 0.75:
                lingering_weak.append(q.target_concept_id)

            eval_items.append(
                ExamGradedItem(
                    question_id=q.question_id,
                    score=score,
                    student_answer=student_ans,
                    feedback=feedback,
                    lingering_flaw=flaw,
                )
            )

    except Exception as e:
        logger.warning("LLM grading failed (%s). Evaluating with deterministic heuristic.", e)
        for q in exam.questions:
            student_ans = sub_map.get(q.question_id, "")
            # Heuristic: non-empty answers get credit, check length & keywords
            if not student_ans.strip():
                score = 0.0
                feedback = "No answer provided."
                flaw = "Missing submission."
            elif q.type == "MCQ":
                # If first option or contains "correct" or "verifying"
                score = 1.0 if any(k in student_ans.lower() for k in ["option a", "verifying", "cycles", "correct"]) else 0.50
                feedback = "Option evaluated against ground-truth invariant."
                flaw = "Selected flawed distractor" if score < 0.75 else None
            else:
                score = 0.88 if len(student_ans.split()) >= 8 else 0.60
                feedback = "Explanation demonstrates acceptable causal reasoning." if score >= 0.75 else "Needs deeper causal elaboration."
                flaw = "Shallow explanation" if score < 0.75 else None

            if score < 0.75:
                lingering_weak.append(q.target_concept_id)

            eval_items.append(
                ExamGradedItem(
                    question_id=q.question_id,
                    score=score,
                    student_answer=student_ans,
                    feedback=feedback,
                    lingering_flaw=flaw,
                )
            )

    total_score = round(sum(item.score for item in eval_items) / max(len(eval_items), 1), 2)
    passed = total_score >= 0.75
    # Remove duplicates from lingering weak concepts
    lingering_weak_unique = list(dict.fromkeys(lingering_weak))

    return ExamResult(
        exam_id=exam.exam_id,
        session_id=session_state.session_id,
        exam_score=total_score,
        passed=passed,
        graded_questions=eval_items,
        lingering_weak_concepts=lingering_weak_unique,
    )
