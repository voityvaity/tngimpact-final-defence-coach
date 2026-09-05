import json
import os
from pathlib import Path
from typing import Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(title="Final Defence Coach", version="1.2.0")
BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() in {"1", "true", "yes", "on"}
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4.1-mini")

Language = Literal["en", "ha"]


class ThesisInput(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    abstract: str = Field(default="", max_length=8000)
    language: Language = "en"


class AnswerInput(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=5000)
    language: Language = "en"


def language_name(language: Language) -> str:
    return "Hausa" if language == "ha" else "English"


def demo_questions(topic: str, language: Language) -> list[str]:
    if language == "ha":
        return [
            f"Wace matsala bincikenka kan '{topic}' yake warwarewa, kuma wa zai fi amfana da sakamakonsa?",
            "Me ya sa ka zabi wannan hanyar bincike, kuma wace hanya ce ka yi la'akari da ita amma ka ki amfani da ita?",
            "Mene ne mafi muhimmancin sakamako daga aikinka, kuma wace shaida ce ta fi goyon bayansa?",
            "Mene ne babban iyakar bincikenka, kuma ta yaya wannan iyakar ke shafar yadda ya kamata a fassara sakamakon?",
            "Idan za ka mayar da wannan bincike zuwa mafita ta zahiri, mene ne mataki na gaba kuma yaya za ka auna nasara?",
        ]

    return [
        f"What problem does your research on '{topic}' solve, and who benefits most from the result?",
        "Why did you choose this methodology, and what alternative approach did you consider but reject?",
        "What is the most important result from your work, and what evidence best supports it?",
        "What is the biggest limitation of your research, and how should that limitation affect interpretation of the results?",
        "If you turned this research into a real-world solution, what would you do next and how would you measure success?",
    ]


def score_dimensions(answer: str) -> dict[str, int]:
    words = answer.split()
    word_count = len(words)
    has_reasoning = any(token in answer.lower() for token in ["because", "therefore", "evidence", "result", "saboda", "sakamako", "shaida"])
    has_structure = any(token in answer.lower() for token in ["first", "second", "finally", "na farko", "sannan", "a karshe"])

    clarity = min(95, 58 + min(27, word_count))
    relevance = min(96, 64 + min(24, word_count // 2))
    evidence = min(94, 50 + min(28, word_count // 2) + (8 if has_reasoning else 0))
    confidence = min(93, 54 + min(25, word_count // 2) + (7 if has_structure else 0))
    return {
        "clarity": clarity,
        "relevance": relevance,
        "evidence": evidence,
        "confidence": confidence,
    }


def demo_evaluation(payload: AnswerInput) -> dict:
    dimensions = score_dimensions(payload.answer)
    score = round(sum(dimensions.values()) / len(dimensions))
    word_count = len(payload.answer.split())

    if payload.language == "ha":
        length_note = "Amsar tana da kyau a tsawo." if word_count >= 25 else "Amsar tana da dan gajarta; kara hujja guda daya takamaimai."
        feedback = (
            f"Ka shiga batun kai tsaye. {length_note} Don kara karfi, fara da babban batu, "
            "ka kawo shaida ko sakamako daya daga binciken, sannan ka bayyana dalilin da ya sa hakan yake da muhimmanci."
        )
        improved = (
            f"Babban batu shi ne cewa bincikena kan {payload.topic} yana magance matsala da aka fayyace. "
            f"Game da tambayar '{payload.question}', zan fara da muhimmin sakamako, in goyi bayansa da shaida daga binciken, "
            "sannan in bayyana abin da wannan sakamakon yake nufi a aikace da kuma wata iyaka idan ta dace."
        )
        next_tip = "Yi kokarin amsa cikin sassa uku: batu, shaida, muhimmanci."
    else:
        length_note = "Your answer has a useful amount of detail." if word_count >= 25 else "Your answer is quite short; add one concrete piece of evidence."
        feedback = (
            f"You answered the question directly. {length_note} To make it stronger, lead with your main claim, "
            "support it with one specific result or piece of evidence, then explain why that evidence matters."
        )
        improved = (
            f"My main point is that my research on {payload.topic} addresses a clearly defined problem. "
            f"For the question '{payload.question}', I would state the key finding first, support it with evidence from the study, "
            "then explain the practical significance and acknowledge a relevant limitation where appropriate."
        )
        next_tip = "Use a three-part answer: claim → evidence → significance."

    return {
        "score": score,
        "dimensions": dimensions,
        "feedback": feedback,
        "improved_answer": improved,
        "next_tip": next_tip,
        "mode": "demo",
        "language": payload.language,
    }


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
    return {"status": "ok", "demo_mode": DEMO_MODE, "languages": ["en", "ha"], "version": "1.2.0"}


@app.post("/api/questions")
async def generate_questions(payload: ThesisInput) -> dict:
    topic = payload.topic.strip()
    abstract = payload.abstract.strip()
    if not topic:
        raise HTTPException(status_code=422, detail="Topic cannot be empty")

    if DEMO_MODE:
        return {"questions": demo_questions(topic, payload.language), "mode": "demo", "language": payload.language}

    target_language = language_name(payload.language)
    context = abstract if abstract else "No abstract was provided. Base the questions on the thesis topic and ask broadly useful defence questions."
    result = await call_llm([
        {
            "role": "system",
            "content": (
                "You are a supportive but rigorous university thesis defence examiner. Return JSON only with a 'questions' array containing exactly five "
                f"concise, varied, challenging but fair questions. Write every question in {target_language}. Cover problem, methodology, evidence, limitations, and practical impact."
            ),
        },
        {
            "role": "user",
            "content": f"Thesis topic: {topic}\n\nResearch context: {context}",
        },
    ])
    questions = result.get("questions")
    if not isinstance(questions, list) or len(questions) != 5 or not all(isinstance(q, str) and q.strip() for q in questions):
        raise HTTPException(status_code=502, detail="LLM did not return exactly five questions")
    return {"questions": questions, "mode": "llm", "language": payload.language}


@app.post("/api/evaluate")
async def evaluate_answer(payload: AnswerInput) -> dict:
    if DEMO_MODE:
        return demo_evaluation(payload)

    target_language = language_name(payload.language)
    result = await call_llm([
        {
            "role": "system",
            "content": (
                "Evaluate a student's thesis defence answer. Return JSON only with: integer 'score' from 0 to 100; object 'dimensions' with integer scores "
                "for clarity, relevance, evidence, and confidence; short 'feedback'; 'improved_answer'; and one-sentence 'next_tip'. "
                f"Be constructive and specific. Write feedback, improved_answer, and next_tip in {target_language}."
            ),
        },
        {
            "role": "user",
            "content": f"Topic: {payload.topic}\nQuestion: {payload.question}\nStudent answer: {payload.answer}",
        },
    ])
    try:
        score = max(0, min(100, int(result["score"])))
        dimensions_raw = result["dimensions"]
        dimensions = {
            key: max(0, min(100, int(dimensions_raw[key])))
            for key in ("clarity", "relevance", "evidence", "confidence")
        }
        feedback = str(result["feedback"])
        improved_answer = str(result["improved_answer"])
        next_tip = str(result["next_tip"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="LLM evaluation format is invalid") from exc

    return {
        "score": score,
        "dimensions": dimensions,
        "feedback": feedback,
        "improved_answer": improved_answer,
        "next_tip": next_tip,
        "mode": "llm",
        "language": payload.language,
    }
