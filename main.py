import json
import os
import re
from io import BytesIO
from pathlib import Path
from typing import Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from pypdf import PdfReader
from pypdf.errors import PdfReadError

load_dotenv()

APP_VERSION = "2.0.0"
BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"
MAX_UPLOAD_BYTES = 6 * 1024 * 1024
MAX_CONTEXT_CHARS = 12_000

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() in {"1", "true", "yes", "on"}
AI_FALLBACK_TO_DEMO = os.getenv("AI_FALLBACK_TO_DEMO", "true").lower() in {"1", "true", "yes", "on"}
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4.1-mini")

app = FastAPI(title="Final Defence Coach", version=APP_VERSION)
Language = Literal["en", "ha"]


class ThesisInput(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    abstract: str = Field(default="", max_length=MAX_CONTEXT_CHARS)
    language: Language = "en"


class AnswerInput(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    question: str = Field(min_length=1, max_length=1200)
    answer: str = Field(min_length=1, max_length=6000)
    language: Language = "en"


def language_name(language: Language) -> str:
    return "Hausa" if language == "ha" else "English"


def panel_templates(language: Language) -> list[dict[str, str]]:
    if language == "ha":
        return [
            {"role": "Mai kula da bincike", "category": "Matsala da tasiri"},
            {"role": "Mai nazarin hanya", "category": "Hanyar bincike"},
            {"role": "Mai duba hujja", "category": "Sakamako da hujja"},
            {"role": "Mai jarrabawa na waje", "category": "Iyakoki"},
            {"role": "Mai duba tasiri", "category": "Amfani a aikace"},
        ]
    return [
        {"role": "Research supervisor", "category": "Problem & impact"},
        {"role": "Methodology examiner", "category": "Methodology"},
        {"role": "Evidence reviewer", "category": "Results & evidence"},
        {"role": "External examiner", "category": "Limitations"},
        {"role": "Impact reviewer", "category": "Practical application"},
    ]


def demo_questions(topic: str, language: Language) -> list[dict[str, str]]:
    if language == "ha":
        questions = [
            f"Wace matsala bincikenka kan '{topic}' yake warwarewa, kuma wa zai fi amfana da sakamakonsa?",
            "Me ya sa ka zabi wannan hanyar bincike, kuma wace hanya ce ka yi la'akari da ita amma ka ki amfani da ita?",
            "Mene ne mafi muhimmancin sakamako daga aikinka, kuma wace shaida ce ta fi goyon bayansa?",
            "Mene ne babban iyakar bincikenka, kuma ta yaya wannan iyakar ke shafar yadda ya kamata a fassara sakamakon?",
            "Idan za ka mayar da wannan bincike zuwa mafita ta zahiri, mene ne mataki na gaba kuma yaya za ka auna nasara?",
        ]
    else:
        questions = [
            f"What problem does your research on '{topic}' solve, and who benefits most from the result?",
            "Why did you choose this methodology, and what alternative approach did you consider but reject?",
            "What is the most important result from your work, and what evidence best supports it?",
            "What is the biggest limitation of your research, and how should that limitation affect interpretation of the results?",
            "If you turned this research into a real-world solution, what would you do next and how would you measure success?",
        ]

    return [
        {"id": f"q{index + 1}", **template, "question": question}
        for index, (template, question) in enumerate(zip(panel_templates(language), questions, strict=True))
    ]


def normalize_questions(raw_questions: object, language: Language) -> list[dict[str, str]]:
    if not isinstance(raw_questions, list) or len(raw_questions) != 5:
        raise ValueError("Exactly five questions are required")

    templates = panel_templates(language)
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(raw_questions):
        if isinstance(item, str):
            question = item.strip()
            role = templates[index]["role"]
            category = templates[index]["category"]
        elif isinstance(item, dict):
            question = str(item.get("question") or item.get("text") or "").strip()
            role = str(item.get("role") or templates[index]["role"]).strip()
            category = str(item.get("category") or templates[index]["category"]).strip()
        else:
            raise ValueError("Question format is invalid")

        if not question:
            raise ValueError("Question cannot be empty")
        normalized.append({"id": f"q{index + 1}", "role": role, "category": category, "question": question})
    return normalized


STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "is", "are", "was", "were", "this", "that",
    "what", "why", "how", "your", "you", "my", "our", "with", "from", "it", "be", "as", "at", "by", "we", "i",
    "da", "na", "ne", "ce", "ya", "ta", "su", "a", "ko", "me", "yaya", "wace", "mene", "kuma", "daga", "don",
}
WORD_RE = re.compile(r"[\w'-]+", re.UNICODE)


def meaningful_words(text: str) -> set[str]:
    return {
        token.lower()
        for token in WORD_RE.findall(text)
        if len(token) > 2 and token.lower() not in STOPWORDS
    }


def score_dimensions(topic: str, question: str, answer: str) -> dict[str, int]:
    words = WORD_RE.findall(answer)
    word_count = len(words)
    answer_lower = answer.lower()
    sentence_count = max(1, len(re.findall(r"[.!?]+", answer)))

    context_terms = meaningful_words(f"{topic} {question}")
    answer_terms = meaningful_words(answer)
    overlap = len(context_terms & answer_terms)

    reasoning_markers = [
        "because", "therefore", "result", "evidence", "data", "found", "showed", "sample", "study",
        "saboda", "don haka", "sakamako", "shaida", "bayanai", "bincike",
    ]
    structure_markers = [
        "first", "second", "finally", "however", "although", "in conclusion", "for example",
        "na farko", "sannan", "a karshe", "amma", "misali",
    ]
    has_reasoning = any(marker in answer_lower for marker in reasoning_markers)
    has_structure = any(marker in answer_lower for marker in structure_markers)
    has_number = bool(re.search(r"\d", answer))

    clarity = 50 + min(28, word_count) + min(8, sentence_count * 2)
    if word_count > 180:
        clarity -= 8
    relevance = 50 + min(34, overlap * 7) + min(10, word_count // 8)
    evidence = 44 + min(20, word_count // 3) + (14 if has_reasoning else 0) + (8 if has_number else 0)
    structure = 48 + min(20, word_count // 4) + (16 if has_structure else 0) + min(8, sentence_count * 2)

    return {
        "clarity": max(35, min(96, clarity)),
        "relevance": max(35, min(96, relevance)),
        "evidence": max(35, min(96, evidence)),
        "structure": max(35, min(96, structure)),
    }


def coaching_copy(language: Language, dimensions: dict[str, int]) -> tuple[list[str], list[str], str]:
    strongest = max(dimensions, key=dimensions.get)
    weakest = min(dimensions, key=dimensions.get)

    if language == "ha":
        labels = {
            "clarity": "bayyananniyar amsa",
            "relevance": "dacewa da tambaya",
            "evidence": "amfani da hujja",
            "structure": "tsarin amsa",
        }
        strengths = [f"Mafi karfin bangaren amsarka shi ne {labels[strongest]}."]
        improvements = [f"Ka fi bukatar inganta {labels[weakest]} a amsa ta gaba."]
        tips = {
            "clarity": "Fara da jimla daya da ke bada amsa kai tsaye kafin karin bayani.",
            "relevance": "Maimaita muhimmin bangaren tambayar sannan ka danganta amsarka da shi kai tsaye.",
            "evidence": "Kara sakamako, adadi, misali ko wata hujja takamaimai daga bincikenka.",
            "structure": "Yi amfani da tsari mai sauki: batu → hujja → muhimmanci → iyaka.",
        }
    else:
        labels = {
            "clarity": "clarity",
            "relevance": "relevance to the question",
            "evidence": "use of evidence",
            "structure": "answer structure",
        }
        strengths = [f"Your strongest area in this response is {labels[strongest]}."]
        improvements = [f"Your biggest opportunity for the next answer is {labels[weakest]}."]
        tips = {
            "clarity": "Lead with one sentence that directly answers the question before adding detail.",
            "relevance": "Echo the key part of the examiner's question and connect every point back to it.",
            "evidence": "Add one concrete result, number, example, or observation from your own research.",
            "structure": "Use a simple structure: claim → evidence → significance → limitation.",
        }
    return strengths, improvements, tips[weakest]


def demo_evaluation(payload: AnswerInput) -> dict:
    dimensions = score_dimensions(payload.topic, payload.question, payload.answer)
    score = round(sum(dimensions.values()) / len(dimensions))
    strengths, improvements, next_tip = coaching_copy(payload.language, dimensions)

    if payload.language == "ha":
        feedback = (
            "An auna amsarka ta fuskar bayyanawa, dacewa da tambaya, hujja, da tsari. "
            "Makin ba ya nuna ko bincikenka daidai ne; yana nuna yadda amsar ta kasance mai saukin karewa a gaban kwamitin."
        )
        improved = (
            "Tsarin da za ka iya amfani da shi:\n"
            "1. Babban batu: [amsa kai tsaye ga tambayar].\n"
            "2. Hujja: [takamaiman sakamako, adadi ko misali daga bincikenka].\n"
            "3. Muhimmanci: [me wannan sakamakon yake nufi].\n"
            "4. Iyakar bincike: [abin da sakamakon ba zai iya tabbatarwa ba]."
        )
    else:
        feedback = (
            "Your response was assessed for clarity, relevance, evidence, and structure. "
            "This score does not judge whether your research is scientifically correct; it reflects how defensible the written answer sounds to a panel."
        )
        improved = (
            "A stronger answer structure you can fill with your real research:\n"
            "1. Main claim: [direct answer to the examiner's question].\n"
            "2. Evidence: [specific result, number, or observation from your study].\n"
            "3. Significance: [why that evidence matters].\n"
            "4. Limitation: [what the result cannot prove or where caution is needed]."
        )

    return {
        "score": score,
        "dimensions": dimensions,
        "strengths": strengths,
        "improvements": improvements,
        "feedback": feedback,
        "improved_answer": improved,
        "next_tip": next_tip,
        "word_count": len(WORD_RE.findall(payload.answer)),
        "mode": "demo",
        "language": payload.language,
    }


def extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


async def call_llm(messages: list[dict]) -> dict:
    if not LLM_API_KEY:
        raise HTTPException(status_code=503, detail="LLM_API_KEY is not configured")

    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    base_body = {"model": LLM_MODEL, "messages": messages, "temperature": 0.25}

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
            for use_json_mode in (True, False):
                body = dict(base_body)
                if use_json_mode:
                    body["response_format"] = {"type": "json_object"}
                response = await client.post(f"{LLM_BASE_URL}/chat/completions", headers=headers, json=body)
                if use_json_mode and response.status_code in {400, 404, 415, 422}:
                    continue
                response.raise_for_status()
                data = response.json()
                return extract_json(data["choices"][0]["message"]["content"])
    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="The AI provider returned an invalid or unavailable response") from exc

    raise HTTPException(status_code=502, detail="The AI provider did not accept the request format")


def fallback_notice(language: Language) -> str:
    if language == "ha":
        return "Ba a samu AI provider ba, don haka an yi amfani da local demo coaching domin kada atisayen ya tsaya."
    return "The AI provider was unavailable, so local demo coaching was used to keep the practice session working."


def suggested_topic_from_text(text: str) -> str:
    for line in text.splitlines():
        candidate = line.strip().lstrip("#").strip()
        if 4 <= len(candidate) <= 180:
            return candidate
    return ""


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "microphone=(self)"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=500, detail="index.html is missing")
    return HTMLResponse(INDEX_FILE.read_text(encoding="utf-8"))


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": APP_VERSION,
        "mode": "demo" if DEMO_MODE else "llm",
        "fallback_to_demo": AI_FALLBACK_TO_DEMO,
        "languages": ["en", "ha"],
        "upload_types": ["pdf", "txt", "md"],
    }


@app.post("/api/extract")
async def extract_research(file: UploadFile = File(...)) -> dict:
    filename = (file.filename or "research").strip()
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".txt", ".md"}:
        raise HTTPException(status_code=415, detail="Use a PDF, TXT, or Markdown file")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large; maximum size is 6 MB")

    try:
        if suffix == ".pdf":
            reader = PdfReader(BytesIO(content))
            text = "\n\n".join((page.extract_text() or "").strip() for page in reader.pages)
        else:
            text = content.decode("utf-8-sig")
    except (PdfReadError, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="The file could not be read as text") from exc

    text = text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="No extractable text was found in this file")

    truncated = len(text) > MAX_CONTEXT_CHARS
    context = text[:MAX_CONTEXT_CHARS]
    return {
        "filename": filename,
        "text": context,
        "suggested_topic": suggested_topic_from_text(context),
        "truncated": truncated,
        "characters": len(context),
    }


@app.post("/api/questions")
async def generate_questions(payload: ThesisInput) -> dict:
    topic = payload.topic.strip()
    abstract = payload.abstract.strip()
    if not topic:
        raise HTTPException(status_code=422, detail="Topic cannot be empty")

    if DEMO_MODE:
        return {"questions": demo_questions(topic, payload.language), "mode": "demo", "language": payload.language}

    target_language = language_name(payload.language)
    context = abstract or "No thesis context was provided. Base the panel on the topic and ask broadly useful defence questions."
    try:
        result = await call_llm([
            {
                "role": "system",
                "content": (
                    "You are a realistic but supportive university thesis defence panel. Return JSON only with a 'questions' array of exactly five objects. "
                    "Each object must contain 'role', 'category', and 'question'. Cover problem/impact, methodology, evidence/results, limitations, and practical application. "
                    f"Write all visible text in {target_language}. Keep each question concise and specific to the provided research when possible."
                ),
            },
            {"role": "user", "content": f"Thesis topic: {topic}\n\nResearch context: {context}"},
        ])
        questions = normalize_questions(result.get("questions"), payload.language)
        return {"questions": questions, "mode": "llm", "language": payload.language}
    except (HTTPException, ValueError) as exc:
        if not AI_FALLBACK_TO_DEMO:
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(status_code=502, detail="The AI panel returned an invalid question format") from exc
        return {
            "questions": demo_questions(topic, payload.language),
            "mode": "fallback",
            "language": payload.language,
            "notice": fallback_notice(payload.language),
        }


@app.post("/api/evaluate")
async def evaluate_answer(payload: AnswerInput) -> dict:
    if DEMO_MODE:
        return demo_evaluation(payload)

    target_language = language_name(payload.language)
    try:
        result = await call_llm([
            {
                "role": "system",
                "content": (
                    "Act as a thesis defence coach. Return JSON only with: object 'dimensions' containing integer 0-100 scores for clarity, relevance, evidence, and structure; "
                    "array 'strengths' with 1-3 concise items; array 'improvements' with 1-3 concise items; short 'feedback'; 'improved_answer'; and one-sentence 'next_tip'. "
                    "Never invent research findings, numbers, citations, or facts that the student did not provide. The improved answer should use placeholders when evidence is missing. "
                    f"Write all coaching text in {target_language}."
                ),
            },
            {
                "role": "user",
                "content": f"Topic: {payload.topic}\nQuestion: {payload.question}\nStudent answer: {payload.answer}",
            },
        ])
        dimensions_raw = result["dimensions"]
        dimensions = {
            key: max(0, min(100, int(dimensions_raw[key])))
            for key in ("clarity", "relevance", "evidence", "structure")
        }
        strengths = [str(item) for item in result["strengths"]][:3]
        improvements = [str(item) for item in result["improvements"]][:3]
        if not strengths or not improvements:
            raise ValueError("Coaching lists cannot be empty")
        response = {
            "score": round(sum(dimensions.values()) / len(dimensions)),
            "dimensions": dimensions,
            "strengths": strengths,
            "improvements": improvements,
            "feedback": str(result["feedback"]),
            "improved_answer": str(result["improved_answer"]),
            "next_tip": str(result["next_tip"]),
            "word_count": len(WORD_RE.findall(payload.answer)),
            "mode": "llm",
            "language": payload.language,
        }
        return response
    except (HTTPException, KeyError, TypeError, ValueError) as exc:
        if not AI_FALLBACK_TO_DEMO:
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(status_code=502, detail="The AI evaluation format was invalid") from exc
        response = demo_evaluation(payload)
        response["mode"] = "fallback"
        response["notice"] = fallback_notice(payload.language)
        return response
