import os
import sys
from pathlib import Path

import pytest

os.environ["DEMO_MODE"] = "true"
os.environ["AI_FALLBACK_TO_DEMO"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from main import app, normalize_questions, score_dimensions

client = TestClient(app)
SUPPORTED = ["en", "ha", "yo", "ig", "sw", "zu"]
FIRST_ROLES = {
    "en": "Research supervisor",
    "ha": "Mai kula da bincike",
    "yo": "Olùtọ́jú ìwádìí",
    "ig": "Onye nlekọta nyocha",
    "sw": "Msimamizi wa utafiti",
    "zu": "Umqondisi wocwaningo",
}


def test_home_page_has_multilingual_african_demo_flow():
    response = client.get("/")
    assert response.status_code == 200
    assert "Final Defence Coach" in response.text
    assert "Multilingual for Africa" in response.text
    assert "English + Hausa" not in response.text
    for language, label in {
        "en": "English",
        "ha": "Hausa",
        "yo": "Yorùbá",
        "ig": "Igbo",
        "sw": "Kiswahili",
        "zu": "isiZulu",
    }.items():
        assert f'<option value="{language}">{label}</option>' in response.text
    assert 'id="guidedDemoBtn"' in response.text
    assert 'id="fileInput"' in response.text
    assert 'id="dictateBtn"' in response.text
    assert 'id="progressBar"' in response.text
    assert 'class="kente-band"' in response.text


def test_health_reports_runtime_capabilities():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "2.1.0",
        "mode": "demo",
        "fallback_to_demo": True,
        "languages": SUPPORTED,
        "upload_types": ["pdf", "txt", "md"],
    }


def test_api_response_has_security_headers():
    response = client.post(
        "/api/questions",
        json={"topic": "Test topic", "abstract": "", "language": "en"},
    )
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("language", SUPPORTED)
def test_generate_five_role_panel_in_every_supported_language(language):
    response = client.post(
        "/api/questions",
        json={"topic": "AI crop support", "abstract": "", "language": language},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "demo"
    assert data["language"] == language
    assert len(data["questions"]) == 5
    assert all(set(item) == {"id", "role", "category", "question"} for item in data["questions"])
    assert len({item["role"] for item in data["questions"]}) == 5
    assert data["questions"][0]["role"] == FIRST_ROLES[language]
    assert all(item["question"].strip() for item in data["questions"])


def test_short_abstract_is_allowed():
    response = client.post(
        "/api/questions",
        json={"topic": "Test topic", "abstract": "short", "language": "en"},
    )
    assert response.status_code == 200
    assert len(response.json()["questions"]) == 5


def test_question_normalizer_accepts_plain_strings_for_provider_compatibility():
    questions = normalize_questions([f"Question {number}" for number in range(1, 6)], "en")
    assert len(questions) == 5
    assert questions[0]["role"] == "Research supervisor"
    assert questions[4]["category"] == "Practical application"


@pytest.mark.parametrize("language", SUPPORTED)
def test_demo_coaching_returns_localized_structure_for_each_language(language):
    response = client.post(
        "/api/evaluate",
        json={
            "topic": "AI crop support",
            "question": "Panel question about the project",
            "answer": "This project addresses delayed support because users need earlier guidance. The result should still be confirmed by a domain expert.",
            "language": language,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "demo"
    assert data["language"] == language
    assert 0 <= data["score"] <= 100
    assert set(data["dimensions"]) == {"clarity", "relevance", "evidence", "structure"}
    assert data["strengths"]
    assert data["improvements"]
    assert data["feedback"]
    assert data["improved_answer"]
    assert data["next_tip"]
    assert data["word_count"] > 0


def test_english_framework_does_not_invent_research_facts():
    response = client.post(
        "/api/evaluate",
        json={
            "topic": "AI crop support",
            "question": "What evidence supports your result?",
            "answer": "The project is intended to give an earlier signal.",
            "language": "en",
        },
    )
    assert response.status_code == 200
    assert "[specific result" in response.json()["improved_answer"]


def test_scoring_rewards_relevant_reasoned_answer_over_one_word_answer():
    weak = score_dimensions("AI crop disease detection", "What problem does it solve?", "Yes")
    strong = score_dimensions(
        "AI crop disease detection",
        "What problem does it solve?",
        "The crop disease detection project addresses delayed identification because farmers need an earlier signal before seeking expert support.",
    )
    assert sum(strong.values()) > sum(weak.values())


def test_extract_plain_text_research_file():
    response = client.post(
        "/api/extract",
        files={
            "file": (
                "thesis.txt",
                b"AI-assisted crop disease detection\nThis study explores an accessible workflow for smallholder farmers.",
                "text/plain",
            )
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "thesis.txt"
    assert data["suggested_topic"] == "AI-assisted crop disease detection"
    assert "smallholder farmers" in data["text"]
    assert data["truncated"] is False


def test_extract_rejects_unsupported_file_type():
    response = client.post(
        "/api/extract",
        files={"file": ("notes.docx", b"not a supported format", "application/octet-stream")},
    )
    assert response.status_code == 415


def test_blank_topic_is_rejected():
    response = client.post(
        "/api/questions",
        json={"topic": " ", "abstract": "Anything", "language": "en"},
    )
    assert response.status_code == 422


def test_unknown_language_is_rejected():
    response = client.post(
        "/api/questions",
        json={"topic": "Test topic", "abstract": "", "language": "xx"},
    )
    assert response.status_code == 422
