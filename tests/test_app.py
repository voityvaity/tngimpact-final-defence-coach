import os

os.environ["DEMO_MODE"] = "true"

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_home_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "Final Defence Coach" in response.text


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "demo_mode": True}


def test_generate_five_questions():
    response = client.post(
        "/api/questions",
        json={
            "topic": "AI for crop disease detection",
            "abstract": "This research explores a lightweight AI approach for detecting crop diseases from images in resource-constrained settings.",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "demo"
    assert len(data["questions"]) == 5
    assert all(isinstance(question, str) and question for question in data["questions"])


def test_evaluate_answer():
    response = client.post(
        "/api/evaluate",
        json={
            "topic": "AI for crop disease detection",
            "question": "What problem does your research solve?",
            "answer": "The project helps identify crop disease earlier so farmers can respond faster and reduce avoidable crop losses.",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "demo"
    assert 0 <= data["score"] <= 100
    assert data["feedback"]
    assert data["improved_answer"]


def test_validation_rejects_short_abstract():
    response = client.post(
        "/api/questions",
        json={"topic": "Test topic", "abstract": "too short"},
    )
    assert response.status_code == 422
