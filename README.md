# Final Defence Coach

A lightweight AI-powered thesis defence practice coach built for the **TNGIMPACT AI Challenge 2026**.

Students often know their research but have limited access to realistic mock-defence practice. Final Defence Coach gives them a fast browser-based way to rehearse examiner questions, practise spoken-style answers, and receive structured coaching.

## What it does

1. Enter a thesis topic. An abstract is optional.
2. Generate five varied mock-panel questions.
3. Pick any question and answer it naturally.
4. Receive a readiness score plus four coaching dimensions:
   - Clarity
   - Relevance
   - Evidence
   - Confidence
5. Review focused feedback, a stronger answer structure, and one next-step tip.

The interface supports **English and Hausa**, and the selected language is used for the generated questions and coaching output.

## Demo-friendly features

- **Use example** fills a complete sample project in one click.
- **Use sample answer** makes the full demo flow testable in seconds.
- No minimum abstract length; the topic alone is enough to begin.
- Draft text is stored only in the current browser with `localStorage` so a refresh does not erase the form.
- Responsive layout for desktop and mobile screens.
- No account or database required.
- `DEMO_MODE=true` works without an API key or paid AI request.

## Challenge fit

The project focuses on a practical education problem: giving students repeatable defence practice when access to supervisors, mock panels, or coaching time is limited.

The build intentionally prioritizes:

- **Real-world impact:** a clear student use case.
- **Technical execution:** FastAPI API, validation, bilingual flows, tests, CI, and optional real LLM integration.
- **Innovation:** localized AI coaching rather than a generic chatbot.
- **UX:** one-click demo data, mobile responsiveness, question selection, score breakdown, copy action, and saved drafts.
- **Presentation:** the complete flow can be demonstrated in a few minutes with no external setup.

## Stack

- Python 3.12+
- FastAPI
- HTML / CSS / JavaScript
- httpx
- pytest
- GitHub Actions

## Quick start

```bash
python -m venv venv
source venv/Scripts/activate   # Git Bash on Windows
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn main:app --reload
```

Open http://127.0.0.1:8000

Then click **Use example** → **Generate 5 defence questions** → **Use sample answer** → **Evaluate my answer**.

## Languages

- English (`en`)
- Hausa (`ha`)

Use the selector in the web interface. API clients can send `"language": "en"` or `"language": "ha"`.

## Demo mode

The default configuration is:

```env
DEMO_MODE=true
```

No API key is required. Demo mode returns deterministic local coaching output, which makes the project easy for judges to test.

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
- `GET /health` — health check, supported languages, version
- `POST /api/questions` — generate five defence questions
- `POST /api/evaluate` — evaluate an answer and return score breakdown + coaching

Example request:

```json
{
  "topic": "AI-assisted crop disease detection for smallholder farmers",
  "abstract": "",
  "language": "en"
}
```

## Tests

```bash
pytest -q
```

The automated suite covers English and Hausa flows, topic-only question generation, short abstracts, score breakdowns, validation, and the demo UI entry points.

## Privacy and scope

This hackathon build does not require accounts and does not include code from any separate private application. In demo mode, no thesis text is sent to an external LLM provider. If real LLM mode is enabled, the selected provider receives the prompt content according to that provider's own terms.

## License

MIT
