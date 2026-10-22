"""Analysis pipeline (docs/plan.md §4). Implemented in step 3 of the plan.

identity (R1) -> ToxIndex prediction + evidence -> local reference data -> rules R2-R9
-> optional LLM narrative -> grounding check (R10) -> AnalysisResult
"""

from app.schemas import AnalysisResult, Check


async def run_analysis(chemical_input: str) -> AnalysisResult:
    raise NotImplementedError


def check_value_grounding(result: AnalysisResult) -> Check:
    """Each prediction's raw_value must equal the value in the referenced trace entry."""
    raise NotImplementedError


def check_tool_refs(result: AnalysisResult) -> Check:
    """Reject/flag any tool_ref that does not exist in the trace."""
    raise NotImplementedError
