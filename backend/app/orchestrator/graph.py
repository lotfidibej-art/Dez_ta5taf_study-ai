import logging
from typing import Any, Dict, Optional, Tuple, TypedDict

from langgraph.graph import END, START, StateGraph

from app.schemas.contracts import (
    AgentActionPayload,
    FadedWorkspacePayload,
    FoundationBoardPayload,
    MisconceptionTrapPayload,
    SessionState,
)

logger = logging.getLogger(__name__)


class OrchestratorState(TypedDict):
    """LangGraph execution state wrapping current session and emitted pedagogical action."""
    session: SessionState
    action: Optional[AgentActionPayload]


# ==============================================================================
# Pedagogical Action Stub Nodes
# ==============================================================================

def foundation_stub(state: OrchestratorState) -> Dict[str, Any]:
    """Agent 4 & 5 Stub: Renders Foundation Board for low mastery (< 0.40)."""
    session = state["session"]
    logger.info("Executing foundation_stub for concept=%s", session.active_concept_id)

    action = FoundationBoardPayload(
        ui_component="FOUNDATION_BOARD",
        concept_id=session.active_concept_id,
        bullet_breakdown=[
            "A recursive function is a routine that solves a task by calling itself on smaller sub-problems.",
            "Every valid recursive call must converge toward an explicit Base Case that stops further execution.",
            "Each nested invocation pushes a new stack frame into memory storing arguments and local scope.",
            "When the base case returns, stack frames unwind in Last-In, First-Out (LIFO) order.",
        ],
        mermaid_diagram=(
            "graph TD\n"
            "    C1[\"factorial(3)\"] --> C2[\"3 * factorial(2)\"]\n"
            "    C2 --> C3[\"2 * factorial(1)\"]\n"
            "    C3 --> B1[\"Base Case: factorial(1) = 1\"]\n"
            "    B1 -->|Unwinds| R1[\"Result = 6\"]"
        ),
        bridge_analogy={
            "source_concept": "Russian Matryoshka Nesting Dolls",
            "target_concept": "Recursive Stack Frames",
            "mapping": "Opening each doll represents calling the function with (n - 1) until reaching the solid center doll (Base Case), then closing them back up.",
        },
        interactive_lab={
            "platform": "Python Tutor Visualization",
            "lab_url": "https://pythontutor.com/visualize.html#mode=edit",
            "instruction": "Step through factorial(3) to watch stack frames allocated and freed in real time.",
        },
        study_habit_nudge="Tip: Never code recursion without writing the Base Case conditional on the very first line.",
    )

    # Update session state technique
    updated_session = session.model_copy(
        update={"last_technique_used": "FOUNDATION_BULLETS_ANALOGY"}
    )
    return {"session": updated_session, "action": action}


def scaffolding_stub(state: OrchestratorState) -> Dict[str, Any]:
    """Agent 6 Stub: Renders Faded Workspace for practice mastery (0.40 .. 0.75)."""
    session = state["session"]
    logger.info("Executing scaffolding_stub for concept=%s", session.active_concept_id)

    action = FadedWorkspacePayload(
        ui_component="FADED_EXAMPLE_WORKSPACE",
        problem_statement="Complete the recursive accumulator function `sum_to_n(n)` which returns 1 + 2 + ... + n.",
        steps=[
            {
                "step_number": 1,
                "step_type": "WORKED",
                "label": "Define Base Condition",
                "code": "if n <= 1:\n    return n",
                "annotation": "Guards against infinite decrement and handles base value.",
            },
            {
                "step_number": 2,
                "step_type": "WORKED",
                "label": "Formulate Recurrence Relation",
                "code": "# Total sum is current value n plus sum of remainder",
                "annotation": "Decomposes sum_to_n(n) into n + sum_to_n(n - 1).",
            },
            {
                "step_number": 3,
                "step_type": "FADED",
                "label": "Fill in Recursive Call",
                "code": "return n + _______",
                "expected_token": "sum_to_n(n - 1)",
                "blank_id": "faded_step_3",
            },
        ],
        active_hint={
            "level": 1,
            "hint_text": "Remember: you must invoke the function itself with the reduced subproblem (n - 1).",
            "contingent_level": session.current_hint_level,
        },
    )

    updated_session = session.model_copy(
        update={"last_technique_used": "FADED_WORKED_EXAMPLE"}
    )
    return {"session": updated_session, "action": action}


def mastery_stub(state: OrchestratorState) -> Dict[str, Any]:
    """Agent 7 Stub: Renders Misconception Trap for deep mastery (> 0.75)."""
    session = state["session"]
    logger.info("Executing mastery_stub for concept=%s", session.active_concept_id)

    action = MisconceptionTrapPayload(
        ui_component="MISCONCEPTION_TRAP",
        scenario_intro=(
            "A fellow student claims their Fibonacci function is 100% complete and verified. "
            "Inspect the implementation and pinpoint the fatal edge-case bug."
        ),
        flawed_artifact=(
            "def fibonacci(n: int) -> int:\n"
            "    # Base case\n"
            "    if n == 1:\n"
            "        return 1\n"
            "    # Recursive step\n"
            "    return fibonacci(n - 1) + fibonacci(n - 2)"
        ),
        artifact_language="python",
        hidden_flaw_tag="MISSING_ZERO_BASE_CASE_INFINITE_LOOP",
    )

    updated_session = session.model_copy(
        update={"last_technique_used": "MISCONCEPTION_TRAP"}
    )
    return {"session": updated_session, "action": action}


# ==============================================================================
# Conditional Edge Router
# ==============================================================================

def route_by_mastery(state: OrchestratorState) -> str:
    """Inspects active concept's mastery rating and selects the appropriate pedagogical tier."""
    session = state["session"]
    active_id = session.active_concept_id

    mastery_rating = 0.0
    for node in session.concept_graph:
        if node.concept_id == active_id:
            mastery_rating = node.mastery_rating
            break

    logger.info(
        "Routing session %s (concept=%s, rating=%.2f)",
        session.session_id,
        active_id,
        mastery_rating,
    )

    if mastery_rating < 0.40:
        return "foundation_stub"
    elif mastery_rating <= 0.75:
        return "scaffolding_stub"
    else:
        return "mastery_stub"


# ==============================================================================
# StateGraph Compilation
# ==============================================================================

builder = StateGraph(OrchestratorState)

builder.add_node("foundation_stub", foundation_stub)
builder.add_node("scaffolding_stub", scaffolding_stub)
builder.add_node("mastery_stub", mastery_stub)

builder.add_conditional_edges(
    START,
    route_by_mastery,
    {
        "foundation_stub": "foundation_stub",
        "scaffolding_stub": "scaffolding_stub",
        "mastery_stub": "mastery_stub",
    },
)

builder.add_edge("foundation_stub", END)
builder.add_edge("scaffolding_stub", END)
builder.add_edge("mastery_stub", END)

orchestrator_graph = builder.compile()


def execute_turn(session_state: SessionState) -> Tuple[SessionState, AgentActionPayload]:
    """Helper entrypoint to execute the LangGraph state machine for a single turn."""
    initial_state: OrchestratorState = {
        "session": session_state,
        "action": None,
    }
    result = orchestrator_graph.invoke(initial_state)
    return result["session"], result["action"]
