# Final Defence Coach

Minimal AI-powered thesis defence practice coach built for the TNGIMPACT AI Challenge 2026.

## What it does

A student enters a thesis topic and short abstract. The app generates five defence-style questions, then evaluates the student's answer and suggests a stronger version.

The project runs in `DEMO_MODE` by default, so judges can test the full flow without an API key. An OpenAI-compatible LLM endpoint can be enabled with environment variables.

## Stack

- Python 3.12+
- FastAPI
- HTML/CSS/JavaScript
- httpx
- pytest

## Quick start

```bash
python -m venv venv
source venv/Scripts/activate   # Git Bash on Windows
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

Open http://127.0.0.1:8000

## Demo mode

The default configuration is:

```env
DEMO_MODE=true
```

No API key is required.

## Optional real LLM mode

Use any provider that exposes an OpenAI-compatible `/chat/completions` endpoint:

```env
DEMO_MODE=false
LLM_API_KEY=your_key_here
LLM_BASE_URL=https://api.example.com/v1
LLM_MODEL=your-model-id
```

Never commit `.env` or API keys.

## API

- `GET /` — web interface
- `GET /health` — health check
- `POST /api/questions` — generate five defence questions
- `POST /api/evaluate` — evaluate an answer

## Tests

```bash
pytest -q
```

## Why this matters

Students often know their research but have little access to realistic defence practice. This lightweight coach gives repeatable questioning and immediate feedback using only a browser and a small backend.

## License

MIT
