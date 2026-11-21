import asyncio
import logging
from typing import Any, Dict, Optional, Tuple, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.explainer_agent import generate_foundation_board
from app.agents.lab_fetcher import fetch_interactive_lab
from app.orchestrator.graph_utils import build_networkx_dag
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
# Helper: Prerequisite Backtracking
# ==============================================================================

def check_and_apply_prerequisite_backtracking(session: SessionState) -> SessionState:
    """Implements Prerequisite Backtracking in the Orchestrator.

    If active_concept.attempts >= 2 and active_concept.mastery_rating < 0.40
    and the node has incoming prerequisites in the DAG:
    1. Finds the weakest prerequisite parent (lowest mastery rating).
    2. Shifts active_concept_id backward to that parent.
    3. Resets status appropriately and logs a clear study habit nudge.
    """
    concept_map = {n.concept_id: n for n in session.concept_graph}
    active_node = concept_map.get(session.active_concept_id)

    if not active_node:
        return session

    if active_node.attempts >= 2 and active_node.mastery_rating < 0.40:
        G = build_networkx_dag(session.concept_graph)
        parent_ids = list(G.predecessors(active_node.concept_id)) if active_node.concept_id in G else []

        if parent_ids:
            # Find the parent with lowest mastery
            weakest_parent_id = min(
                parent_ids,
                key=lambda pid: concept_map[pid].mastery_rating if pid in concept_map else 0.0,
            )
            weakest_parent = concept_map.get(weakest_parent_id)
            parent_title = weakest_parent.title if weakest_parent else weakest_parent_id

            logger.info(
                "Backtracking triggered for session %s: shifting active_concept from %s to weakest prerequisite %s (attempts=%d, rating=%.2f)",
                session.session_id,
                active_node.concept_id,
                weakest_parent_id,
                active_node.attempts,
                active_node.mastery_rating,
            )

            # Update statuses
            for node in session.concept_graph:
                if node.concept_id == weakest_parent_id:
                    node.status = "ACTIVE"
                elif node.concept_id == active_node.concept_id:
                    node.status = "LOCKED"

            return session.model_copy(
                update={
                    "active_concept_id": weakest_parent_id,
                    "last_technique_used": "PREREQUISITE_BACKTRACKING",
                }
            )

    return session


# ==============================================================================
# Pedagogical Nodes
# ==============================================================================

def foundation_node(state: OrchestratorState) -> Dict[str, Any]:
    """Agent 4 (Explainer) + Agent 5 (Lab Fetcher) Node for mastery < 0.40.

    1. Checks for prerequisite backtracking if the student is struggling repeatedly.
    2. Runs Agent 4 (Explainer) to generate FoundationBoardPayload.
    3. Runs Agent 5 (Interactive Lab Fetcher) in parallel/concurrently if ENRICHED_EXTERNAL.
    4. Attaches interactive_lab to FoundationBoardPayload if available.
    """
    session = state["session"]
    logger.info("Executing foundation_node for session=%s, concept=%s", session.session_id, session.active_concept_id)

    # 1. Check prerequisite backtracking
    session = check_and_apply_prerequisite_backtracking(session)

    # Find the current active concept node
    concept_map = {n.concept_id: n for n in session.concept_graph}
    active_node = concept_map.get(session.active_concept_id)

    # 2. Parallel execution of Agent 4 and Agent 5
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as executor:
        f_board = executor.submit(generate_foundation_board, session, None)
        f_lab = None
        if session.resource_scope == "ENRICHED_EXTERNAL" and active_node:
            f_lab = executor.submit(
                fetch_interactive_lab, active_node, session.resource_scope, session.domain, None
            )
        board_payload = f_board.result()
        lab_result = f_lab.result() if f_lab else None

    # Attach interactive lab to payload if discovered
    if lab_result:
        board_payload.interactive_lab = lab_result

    # Increment attempt count on active node
    for node in session.concept_graph:
        if node.concept_id == session.active_concept_id:
            node.attempts += 1
            break

    updated_session = session.model_copy(
        update={
            "concept_graph": session.concept_graph,
            "last_technique_used": "FOUNDATION_BULLETS_ANALOGY",
        }
    )
    return {"session": updated_session, "action": board_payload}


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

    for node in session.concept_graph:
        if node.concept_id == session.active_concept_id:
            node.attempts += 1
            break

    updated_session = session.model_copy(
        update={
            "concept_graph": session.concept_graph,
            "last_technique_used": "FADED_WORKED_EXAMPLE",
        }
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

    for node in session.concept_graph:
        if node.concept_id == session.active_concept_id:
            node.attempts += 1
            break

    updated_session = session.model_copy(
        update={
            "concept_graph": session.concept_graph,
            "last_technique_used": "MISCONCEPTION_TRAP",
        }
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
        return "foundation_node"
    elif mastery_rating <= 0.75:
        return "scaffolding_stub"
    else:
        return "mastery_stub"


# ==============================================================================
# StateGraph Compilation
# ==============================================================================

builder = StateGraph(OrchestratorState)

builder.add_node("foundation_node", foundation_node)
builder.add_node("scaffolding_stub", scaffolding_stub)
builder.add_node("mastery_stub", mastery_stub)

builder.add_conditional_edges(
    START,
    route_by_mastery,
    {
        "foundation_node": "foundation_node",
        "scaffolding_stub": "scaffolding_stub",
        "mastery_stub": "mastery_stub",
    },
)

builder.add_edge("foundation_node", END)
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
