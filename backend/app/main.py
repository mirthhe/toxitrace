from fastapi import FastAPI, HTTPException, Query, Response

from app import chem, replay
from app.agent import run_analysis
from app.config import settings
from app.identity import InvalidInput
from app.schemas import AnalysisRequest, AnalysisResult

app = FastAPI(title="ToxiTrace")


@app.get("/api/health")
async def health() -> dict:
    """Also tells the UI whether results come from live APIs or recorded responses."""
    offline = settings.toxitrace_offline
    return {
        "status": "ok",
        "mode": "offline" if offline else "live",
        "demo_inputs": replay.DEMO_INPUTS,
        "toxindex_key_configured": bool(settings.toxindex_api_key),
    }


@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze(request: AnalysisRequest) -> AnalysisResult:
    try:
        return await run_analysis(request.chemical_input.strip())
    except InvalidInput as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/depict")
async def depict(smiles: str = Query(min_length=1, max_length=2000)) -> Response:
    svg = chem.depict_svg(smiles)
    if svg is None:
        raise HTTPException(status_code=400, detail="Could not parse the SMILES.")
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "max-age=86400"})
