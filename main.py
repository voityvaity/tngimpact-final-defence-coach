import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(title="Final Defence Coach", version="1.0.0")
BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() in {"1", "true", "yes", "on"}
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4.1-mini")


class ThesisInput(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    abstract: str = Field(min_length=20, max_length=8000)


class AnswerInput(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    question: str = Field(min_length=3, max_length=1000)
    answer: str = Field(min_length=2, max_length=5000)


def demo_questions(topic: str) -> list[str]:
    return [
        f"What problem does your research on '{topic}' solve, and why is it important?",
        "What methodology did you choose, and why was it appropriate for this study?",
        "What is the most important result or insight from your work?",
        "What are the main limitations of your research?",
        "If you had more time or resources, what would you improve or investigate next?",
    ]


def demo_evaluation(payload: AnswerInput) -> dict:
    words = payload.answer.split()
    word_count = len(words)
    score = min(92, 45 + min(35, word_count // 2))

    strengths = "You answered the question directly"
    if word_count >= 35:
        strengths += " and provided useful detail"
    else:
        strengths += ", but the answer is quite short"

    feedback = (
        f"{strengths}. Make the response stronger by stating your main point first, "
        "supporting it with one concrete detail from the research, and ending with the significance of that detail."
    )

    improved = (
        f"My main point is that this work on {payload.topic} addresses a clearly defined research problem. "
        f"In response to the question '{payload.question}', I would first state the key finding or decision, "
        "then support it with evidence from the study, explain the reasoning behind it, and acknowledge any relevant limitation. "
        "This makes the answer concise, defensible, and connected to the research objective."
    )

    return {"score": score, "feedback": feedback, "improved_answer": improved, "mode": "demo"}


def extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].lstrip()
    return json.loads(cleaned)


async def call_llm(messages: list[dict]) -> dict:
    if not LLM_API_KEY:
        raise HTTPException(status_code=503, detail="LLM_API_KEY is not configured")

    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(f"{LLM_BASE_URL}/chat/completions", headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
            return extract_json(data["choices"][0]["message"]["content"])
    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="LLM provider returned an invalid response") from exc


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=500, detail="index.html is missing")
    return HTMLResponse(INDEX_FILE.read_text(encoding="utf-8"))


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "demo_mode": DEMO_MODE}


@app.post("/api/questions")
async def generate_questions(payload: ThesisInput) -> dict:
    if DEMO_MODE:
        return {"questions": demo_questions(payload.topic), "mode": "demo"}

    result = await call_llm([
        {
            "role": "system",
            "content": "You are a university thesis defence examiner. Return JSON only with a 'questions' array containing exactly five concise, challenging but fair questions.",
        },
        {
            "role": "user",
            "content": f"Thesis topic: {payload.topic}\n\nAbstract: {payload.abstract}",
        },
    ])
    questions = result.get("questions")
    if not isinstance(questions, list) or len(questions) != 5 or not all(isinstance(q, str) for q in questions):
        raise HTTPException(status_code=502, detail="LLM did not return exactly five questions")
    return {"questions": questions, "mode": "llm"}


@app.post("/api/evaluate")
async def evaluate_answer(payload: AnswerInput) -> dict:
    if DEMO_MODE:
        return demo_evaluation(payload)

    result = await call_llm([
        {
            "role": "system",
            "content": "Evaluate a student's thesis defence answer. Return JSON only with integer 'score' from 0 to 100, short 'feedback', and 'improved_answer'. Be constructive and specific.",
        },
        {
            "role": "user",
            "content": f"Topic: {payload.topic}\nQuestion: {payload.question}\nStudent answer: {payload.answer}",
        },
    ])
    try:
        score = int(result["score"])
        feedback = str(result["feedback"])
        improved_answer = str(result["improved_answer"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="LLM evaluation format is invalid") from exc

    return {
        "score": max(0, min(100, score)),
        "feedback": feedback,
        "improved_answer": improved_answer,
        "mode": "llm",
    }
