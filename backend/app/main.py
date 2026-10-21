from fastapi import FastAPI

from app.agent import run_analysis
from app.schemas import AnalysisRequest, AnalysisResult

app = FastAPI(title="ToxiTrace")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze(request: AnalysisRequest) -> AnalysisResult:
    return await run_analysis(request.chemical_input.strip())
