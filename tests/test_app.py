import os
import sys
from pathlib import Path

os.environ["DEMO_MODE"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_home_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "Final Defence Coach" in response.text
    assert '<option value="ha">Hausa</option>' in response.text


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "demo_mode": True, "languages": ["en", "ha"]}


def test_generate_five_questions_in_english():
    response = client.post(
        "/api/questions",
        json={
            "topic": "AI for crop disease detection",
            "abstract": "This research explores a lightweight AI approach for detecting crop diseases from images in resource-constrained settings.",
            "language": "en",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "demo"
    assert data["language"] == "en"
    assert len(data["questions"]) == 5
    assert all(isinstance(question, str) and question for question in data["questions"])


def test_generate_five_questions_in_hausa():
    response = client.post(
        "/api/questions",
        json={
            "topic": "AI wajen gano cututtukan amfanin gona",
            "abstract": "Wannan bincike yana amfani da AI mai sauki domin gano cututtukan amfanin gona daga hotuna a wuraren da kayan aiki suke da karanci.",
            "language": "ha",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "demo"
    assert data["language"] == "ha"
    assert len(data["questions"]) == 5
    assert "Wace matsala" in data["questions"][0]


def test_evaluate_answer_in_english():
    response = client.post(
        "/api/evaluate",
        json={
            "topic": "AI for crop disease detection",
            "question": "What problem does your research solve?",
            "answer": "The project helps identify crop disease earlier so farmers can respond faster and reduce avoidable crop losses.",
            "language": "en",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "demo"
    assert data["language"] == "en"
    assert 0 <= data["score"] <= 100
    assert data["feedback"]
    assert data["improved_answer"]


def test_evaluate_answer_in_hausa():
    response = client.post(
        "/api/evaluate",
        json={
            "topic": "AI wajen gano cututtukan amfanin gona",
            "question": "Wace matsala bincikenka yake warwarewa?",
            "answer": "Aikin yana taimakawa wajen gano cutar amfanin gona da wuri domin manoma su dauki mataki cikin sauri.",
            "language": "ha",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "demo"
    assert data["language"] == "ha"
    assert 0 <= data["score"] <= 100
    assert data["feedback"]
    assert data["improved_answer"]


def test_validation_rejects_short_abstract():
    response = client.post(
        "/api/questions",
        json={"topic": "Test topic", "abstract": "too short", "language": "en"},
    )
    assert response.status_code == 422


def test_validation_rejects_unknown_language():
    response = client.post(
        "/api/questions",
        json={
            "topic": "Test topic",
            "abstract": "This abstract is definitely long enough to pass the minimum validation length.",
            "language": "xx",
        },
    )
    assert response.status_code == 422
