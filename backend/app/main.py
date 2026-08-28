from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.models import VerifyRequest, VerifyResponse
from app.services.verifier import verify


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

app = FastAPI(
    title="VerifyIt API",
    version="0.2.0",
    description="Evidence-backed verification API for claims, links, posts, and media.",
)

WEB_INDEX = ROOT_DIR / "web" / "index.html"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "verifyit"}


@app.post("/api/v1/verify", response_model=VerifyResponse)
def verify_content(payload: VerifyRequest) -> VerifyResponse:
    return verify(payload)


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(WEB_INDEX)
