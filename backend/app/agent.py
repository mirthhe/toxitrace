"""Analysis pipeline (docs/plan.md §4).

identity (R1) -> ToxIndex prediction + evidence -> local reference data -> rules R2-R9
-> optional LLM narrative -> grounding check (R10) -> AnalysisResult

Implemented so far: identity (R1). Later steps are added rule by rule.
"""

from app.identity import resolve_identity
from app.schemas import AnalysisResult
from app.trace import Tracer

ENDPOINT = "ames_mutagenicity"


async def run_analysis(chemical_input: str) -> AnalysisResult:
    tracer = Tracer()
    identity, flags = await resolve_identity(chemical_input, tracer)
    return AnalysisResult(
        chemical_input=chemical_input,
        endpoint=ENDPOINT,
        identity=identity,
        flags=flags,
        trace=tracer.entries,
    )
