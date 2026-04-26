# ClearConsent Backend

AI-powered consent and document analysis API built with FastAPI for the **BearHacks** hackathon.

## Architecture

```
backend/
  app/
    main.py                 # FastAPI app, CORS, health check
    routes/
      analyze.py            # POST /api/analyze, /api/analyze/mock, /api/analyze/dcp
      history.py            # GET  /api/history/{user_id}
    services/
      model_service.py      # Hybrid classifier (rules + DistilBERT)
      vision_service.py     # Google Cloud Vision OCR (+ mock fallback)
      gemma_service.py      # Gemini/Gemma LLM explanations (+ fallback)
      backboard_service.py  # Backboard consent vault (+ in-memory fallback)
      dcp_service.py        # DCP parallel processing (+ simulation)
      mock_data.py          # Polished instant-demo response
    models/
      schemas.py            # Pydantic response schemas
  requirements.txt
  .env.example
```

## Quick Start

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # Edit with your API keys (or leave blank for mock mode)
uvicorn app.main:app --reload --port 8000
```

The API launches on **http://localhost:8000**. Open **http://localhost:8000/docs** for the interactive Swagger UI.

## Endpoints

| Method | Path                         | Description                              |
| ------ | ---------------------------- | ---------------------------------------- |
| GET    | `/health`                    | Health check + integration status        |
| POST   | `/api/analyze`               | Full analysis pipeline (upload a file)   |
| POST   | `/api/analyze/mock`          | Instant polished demo response           |
| POST   | `/api/analyze/dcp`           | DCP parallel-processing demo             |
| GET    | `/api/history/{user_id}`     | Consent vault scan history               |

## Sponsor Integrations

Every integration has a **real mode** (when the API key is set) and a **safe mock fallback** (when it is not):

| Integration          | Env Var                          | Fallback Behaviour                          |
| -------------------- | -------------------------------- | ------------------------------------------- |
| Google Cloud Vision  | `GOOGLE_APPLICATION_CREDENTIALS` | Returns realistic mock OCR text             |
| Custom DistilBERT    | `CLEARCONSENT_MODEL_DIR`         | Rule-based classifier only                  |
| Google Gemma / Gemini| `GEMINI_API_KEY`                 | Deterministic plain-English translations    |
| Backboard            | `BACKBOARD_API_KEY`              | In-memory consent vault                     |
| DCP / Distributive   | `DCP_API_KEY`                    | Simulated parallel timing metrics           |

## Custom ML Model

The backend loads a fine-tuned **DistilBERT** model from `../ml/clearconsent-distilbert-v2`. This is a multi-label classifier trained on legal clause data that predicts 9 risk categories:

- WAIVER_OF_RIGHTS
- ARBITRATION
- LIABILITY_LIMITATION
- FINANCIAL_LIABILITY
- AUTO_RENEWAL
- TERMINATION
- EMPLOYMENT_RESTRICTION
- LEGAL_JURISDICTION
- LIMITED_PROTECTION

The hybrid classifier combines DistilBERT predictions with deterministic rule-based matching for must-catch categories to ensure demo reliability.

## Hackathon Theme

**"Break the Norm."** The norm we are breaking: people are expected to blindly sign documents they do not understand. ClearConsent gives everyone the power to understand what they are agreeing to.
