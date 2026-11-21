import json
from pydantic import BaseModel, Field
from typing import Optional
from app.services.llm_client import GeminiLLMClient

class EvaluationResult(BaseModel):
    likely_concept_evaluated: str = Field(..., description="The probable scientific/engineering concept the student is discussing.")
    factual_accuracy: float = Field(..., ge=0.0, le=1.0, description="Factual accuracy score between 0 and 1.")
    causal_depth_score: float = Field(..., ge=0.0, le=1.0, description="Depth of causal reasoning between 0 and 1.")
    prosody_fluency_score: float = Field(..., ge=0.0, le=1.0, description="Speech fluency, cadence, and delivery score between 0 and 1.")
    comprehension_rating: float = Field(..., ge=0.0, le=1.0, description="Final fused comprehension rating between 0.0 and 1.0.")
    identified_misconception: Optional[str] = Field(None, description="Specific error or inversion in logic.")
    detailed_pedagogical_feedback: str = Field(..., description="Actionable breakdown of what the student got right, what was confused, and the recommended intervention tier.")

llm = GeminiLLMClient()
prompt = """
You are Agent 3 (Evaluator & Prosody Grader) in an Adaptive AI Learning Platform.
Evaluate this student oral explanation:

STUDENT TRANSCRIPT:
"If the signal is stationary, it is obligatory, but if it is targeted, it is not necessary, it is stationary."

PROSODY & COGNITIVE TELEMETRY:
- Speech rate: 84.75 WPM (deliberate, steady tempo)
- Inter-word hesitation pauses (>1.5s): 0
- Max pause: 0.70s
- Filler word ratio: 0.0 (no um, uh, like)
- Monotone recitation flag: False

CONTEXT & PHONETIC ANALYSIS:
The student is attempting to state a foundational theorem in Signal Processing / Stochastic Processes:
The relationship between Stationarity and Ergodicity (or 'ergodique' in French, which transcribed phonetically as 'targeted' / 'obligatory').
In stochastic signal theory:
1. Every Ergodic process is strictly stationary (Ergodicity implies Stationarity).
2. A Stationary process is NOT necessarily ergodic (Stationarity does not imply Ergodicity).

Notice what the student said:
- "If the signal is stationary, it is obligatory [ergodic?]" -> Inverted / incorrect. Stationarity does NOT guarantee ergodicity.
- "...but if it is targeted [ergodic], it is not necessary it is stationary" -> Inverted / incorrect. If it is ergodic, it IS necessarily stationary!

Evaluate the student's factual accuracy, causal depth, cognitive delivery, and calculate an overall comprehension_rating (0.0 to 1.0).
"""

res = llm.generate_structured(prompt, EvaluationResult, tier="reasoning")
print(json.dumps(res.model_dump(), indent=2))
