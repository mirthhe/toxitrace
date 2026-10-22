from fastapi import FastAPI, Header, HTTPException

from app import mode, replay
from app.agent import run_analysis
from app.config import settings
from app.identity import InvalidInput
from app.schemas import AnalysisRequest, AnalysisResult

app = FastAPI(title="ToxiTrace")


@app.get("/api/health")
async def health(x_access_code: str | None = Header(default=None)) -> dict:
    """Also tells the UI whether results come from live APIs or recorded responses."""
    offline, _ = mode.resolve(x_access_code)
    return {
        "status": "ok",
        "mode": "offline" if offline else "live",
        "demo_inputs": replay.DEMO_INPUTS,
        "toxindex_key_configured": bool(settings.toxindex_api_key),
        "access_code_required": bool(settings.demo_access_code),
        "access_code_rejected": bool(x_access_code) and not mode.access_granted(x_access_code),
    }


@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze(request: AnalysisRequest, x_access_code: str | None = Header(default=None)) -> AnalysisResult:
    offline, llm = mode.resolve(x_access_code)
    if settings.demo_access_code and not offline and not mode.live_limit.allow(settings.live_analyses_per_hour):
        raise HTTPException(status_code=429, detail="Live analysis limit reached for this hour. Try again later.")
    try:
        with mode.use(offline, llm):
            return await run_analysis(request.chemical_input.strip())
    except InvalidInput as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
