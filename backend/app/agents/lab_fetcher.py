import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
from pydantic import BaseModel, Field

from app.schemas.contracts import ConceptNodeState
from app.services.llm_client import GeminiLLMClient, get_llm_client
from app.services.local_models import LocalMLService

logger = logging.getLogger(__name__)

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "data" / "labs_registry.json"

_CACHED_REGISTRY: Optional[List[Dict[str, Any]]] = None
_CACHED_LAB_EMBEDDINGS: Optional[List[np.ndarray]] = None


class TailoredLabGoal(BaseModel):
    experiment_goal: str = Field(
        ...,
        description="One crisp, active sentence instructing the student on a specific action to take in the lab matching their concept.",
    )


def _load_registry() -> List[Dict[str, Any]]:
    global _CACHED_REGISTRY
    if _CACHED_REGISTRY is None:
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                _CACHED_REGISTRY = json.load(f)
            logger.info("Loaded %d interactive labs from registry", len(_CACHED_REGISTRY))
        except Exception as e:
            logger.error("Failed to load labs_registry.json: %s", e)
            _CACHED_REGISTRY = []
    return _CACHED_REGISTRY


def _get_or_compute_lab_embeddings(labs: List[Dict[str, Any]]) -> List[np.ndarray]:
    global _CACHED_LAB_EMBEDDINGS
    if _CACHED_LAB_EMBEDDINGS is not None and len(_CACHED_LAB_EMBEDDINGS) == len(labs):
        return _CACHED_LAB_EMBEDDINGS

    ml_service = LocalMLService.get_instance()
    texts = [f"{lab['title']}: {lab['description']}" for lab in labs]
    try:
        embeddings = ml_service.embed_text(texts)
        _CACHED_LAB_EMBEDDINGS = [np.array(e, dtype=np.float32) for e in embeddings]
        logger.info("Pre-computed %d lab embeddings", len(embeddings))
    except Exception as e:
        logger.error("Error computing lab embeddings: %s", e)
        _CACHED_LAB_EMBEDDINGS = [np.zeros(384, dtype=np.float32) for _ in labs]

    return _CACHED_LAB_EMBEDDINGS


def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / (norm1 * norm2))


def fetch_interactive_lab(
    active_concept: ConceptNodeState,
    resource_scope: str = "ENRICHED_EXTERNAL",
    domain: Optional[str] = None,
    llm: Optional[GeminiLLMClient] = None,
) -> Optional[Dict[str, str]]:
    """Agent 5: Interactive Lab Matcher.

    1. Enforces resource_scope check: If STRICT_UPLOAD_ONLY, external labs are suppressed.
    2. Computes embedding of active concept (title + summary_hook).
    3. Matches against embedded descriptions in labs_registry.json via cosine similarity.
    4. If top cosine similarity > 0.62 and ENRICHED_EXTERNAL, calls Gemini Fast tier
       to generate a custom 1-sentence experiment_goal.
    """
    if resource_scope == "STRICT_UPLOAD_ONLY":
        logger.info(
            "Agent 5: resource_scope is STRICT_UPLOAD_ONLY. Suppressing external interactive lab."
        )
        return None

    labs = _load_registry()
    if not labs:
        return None

    ml_service = LocalMLService.get_instance()
    concept_query = f"{active_concept.title}. {active_concept.summary_hook or ''}".strip()
    try:
        concept_vecs = ml_service.embed_text([concept_query])
        if not concept_vecs:
            return None
        concept_vec = np.array(concept_vecs[0], dtype=np.float32)
    except Exception as e:
        logger.warning("Agent 5: Failed to embed concept query (%s): %s", concept_query, e)
        return None

    lab_embeddings = _get_or_compute_lab_embeddings(labs)

    best_lab: Optional[Dict[str, Any]] = None
    best_score: float = -1.0
    domain_fallback_lab: Optional[Dict[str, Any]] = None

    for lab, emb in zip(labs, lab_embeddings):
        score = _cosine_similarity(concept_vec, emb)
        # Slight domain affinity bonus if domain matches
        if domain and lab.get("domain", "").lower() == domain.lower():
            score += 0.08
            if domain_fallback_lab is None:
                domain_fallback_lab = lab
        if score > best_score:
            best_score = score
            best_lab = lab

    logger.info(
        "Agent 5: Best lab match for '%s' is '%s' (similarity=%.3f, threshold=0.50)",
        active_concept.title,
        best_lab["title"] if best_lab else "None",
        best_score,
    )

    if best_score < 0.50 or best_lab is None:
        if domain_fallback_lab:
            logger.info("Agent 5: Using domain fallback lab '%s'", domain_fallback_lab["title"])
            best_lab = domain_fallback_lab
        else:
            logger.info("Agent 5: No interactive lab crossed the threshold and no domain fallback found.")
            return None

    # Step 2: Tailor 1-sentence experiment_goal via fast LLM tier
    client = llm or get_llm_client()
    tailored_goal = best_lab.get("default_instruction", "Interact with the controls to explore this concept.")

    try:
        prompt = (
            f"Concept: {active_concept.title}\n"
            f"Summary: {active_concept.summary_hook or ''}\n"
            f"Interactive Sandbox: {best_lab['title']} ({best_lab['platform']})\n"
            f"Sandbox Capability: {best_lab['description']}\n\n"
            "Write exactly ONE concrete, actionable instruction sentence telling the student "
            "what specific slider, parameter, or step to manipulate in this lab to observe the concept's causal behavior."
        )
        system_instruction = (
            "You are Agent 5 (Interactive Lab & Experiment Designer). "
            "Output a single, high-clarity imperative sentence directing student action."
        )
        result: TailoredLabGoal = client.generate_structured(
            prompt=prompt,
            schema=TailoredLabGoal,
            tier="fast",
            system_instruction=system_instruction,
            temperature=0.2,
        )
        if result and result.experiment_goal:
            tailored_goal = result.experiment_goal.strip()
    except Exception as e:
        logger.warning("Agent 5: LLM tailoring failed (%s), using default lab instruction.", e)

    return {
        "platform": best_lab["platform"],
        "lab_url": best_lab["embed_url"],
        "instruction": tailored_goal,
        "title": best_lab["title"],
    }
