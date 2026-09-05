import os
import sys
from pathlib import Path

os.environ["DEMO_MODE"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_home_page_has_bilingual_example_flow():
    response = client.get("/")
    assert response.status_code == 200
    assert "Final Defence Coach" in response.text
    assert '<option value="ha">Hausa</option>' in response.text
    assert 'id="exampleBtn"' in response.text
    assert 'id="sampleAnswerBtn"' in response.text


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "demo_mode": True,
        "languages": ["en", "ha"],
        "version": "1.2.0",
    }


def test_generate_five_questions_in_english_with_no_abstract():
    response = client.post(
        "/api/questions",
        json={
            "topic": "AI for crop disease detection",
            "abstract": "",
            "language": "en",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "demo"
    assert data["language"] == "en"
    assert len(data["questions"]) == 5
    assert all(isinstance(question, str) and question for question in data["questions"])


def test_short_abstract_is_allowed():
    response = client.post(
        "/api/questions",
        json={
            "topic": "Test topic",
            "abstract": "short",
            "language": "en",
        },
    )
    assert response.status_code == 200
    assert len(response.json()["questions"]) == 5


def test_generate_five_questions_in_hausa():
    response = client.post(
        "/api/questions",
        json={
            "topic": "AI wajen gano cututtukan amfanin gona",
            "abstract": "Wannan bincike yana amfani da AI domin taimaka wa kananan manoma.",
            "language": "ha",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "demo"
    assert data["language"] == "ha"
    assert len(data["questions"]) == 5
    assert "Wace matsala" in data["questions"][0]


def test_evaluate_answer_returns_score_breakdown_in_english():
    response = client.post(
        "/api/evaluate",
        json={
            "topic": "AI for crop disease detection",
            "question": "What problem does your research solve?",
            "answer": "The project helps identify crop disease earlier because farmers can act faster and reduce avoidable crop losses.",
            "language": "en",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "demo"
    assert data["language"] == "en"
    assert 0 <= data["score"] <= 100
    assert set(data["dimensions"]) == {"clarity", "relevance", "evidence", "confidence"}
    assert all(0 <= value <= 100 for value in data["dimensions"].values())
    assert data["feedback"]
    assert data["improved_answer"]
    assert data["next_tip"]


def test_evaluate_answer_in_hausa():
    response = client.post(
        "/api/evaluate",
        json={
            "topic": "AI wajen gano cututtukan amfanin gona",
            "question": "Wace matsala bincikenka yake warwarewa?",
            "answer": "Aikin yana taimakawa wajen gano cutar amfanin gona da wuri saboda manoma su dauki mataki cikin sauri.",
            "language": "ha",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "ha"
    assert data["dimensions"]
    assert data["feedback"]
    assert data["next_tip"]


def test_blank_topic_is_rejected():
    response = client.post(
        "/api/questions",
        json={"topic": " ", "abstract": "Anything", "language": "en"},
    )
    assert response.status_code == 422


def test_unknown_language_is_rejected():
    response = client.post(
        "/api/questions",
        json={
            "topic": "Test topic",
            "abstract": "",
            "language": "xx",
        },
    )
    assert response.status_code == 422
