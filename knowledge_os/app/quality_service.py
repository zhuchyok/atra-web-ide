import asyncio
import logging

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Quality Pipeline Service")


class QualityRequest(BaseModel):
    prompt: str
    response: str
    enable_full: bool = False


class QualityResponse(BaseModel):
    enhanced_response: str
    quality: float
    confidence: float
    passed: bool
    issues: list = []


_quality_config = {"reflection": True, "ensemble": True, "fact_check": True, "threshold": 0.7}


def check_confidence(response: str) -> float:
    text_lower = response.lower()
    low_indicators = ["возможно", "вероятно", "not sure", "probably", "maybe"]
    for ind in low_indicators:
        if ind in text_lower:
            return 0.4
    has_headers = any(m in response for m in ["##", "**", "1.", "2."])
    if has_headers:
        return 0.85
    return 0.7


def self_reflect(response: str) -> str:
    issues = []
    if "????" in response:
        issues.append("has_placeholders")
    if len(response) < 50:
        issues.append("too_short")
    return response


@app.post("/quality/enhance", response_model=QualityResponse)
async def enhance(request: QualityRequest):
    confidence = check_confidence(request.response)
    quality = confidence

    issues = []
    if _quality_config["reflection"]:
        if "????" in request.response:
            issues.append("has_placeholders")

    if confidence < 0.6 and _quality_config["ensemble"]:
        ensemble_issues = []
        if "not sure" in request.response.lower():
            ensemble_issues.append("uncertain")
        if len(request.response) > 5000:
            ensemble_issues.append("too_verbose")
        issues.extend(ensemble_issues)

    if _quality_config["fact_check"]:
        hedge_words = ["might", "could", "possibly"]
        hedge_count = sum(1 for w in hedge_words if w in request.response.lower())
        if hedge_count > 3:
            issues.append("too_many_hedge_words")

    passed = quality >= _quality_config["threshold"]

    return QualityResponse(
        enhanced_response=request.response,
        quality=quality,
        confidence=confidence,
        passed=passed,
        issues=issues,
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "quality-pipeline"}


@app.get("/quality/config")
async def config():
    return _quality_config


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)
