# Order Explorer Site

## Project Structure
- `backend/`: FastAPI application (reads the data/ SQLite databases directly, and also serves the exercise tracker — see `EXERCISE_TRACKER.md`)
- `frontend/`: React Vite application (dashboard, orders, budget, categories, wiki, webcams, WhatsApp, and exercise tracker pages)

## Prerequisites
- Python 3.9+
- Node.js 20.19+ (or 22.12+) — required by Vite 7/React 19

## Setup & Run

Docker Compose is the primary deployment path for the whole stack (see the
root [README.md](../README.md#docker-deployment)). To run just this site
manually instead:

### 1. Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8015
```
(Run from `order_explorer_site` root if running `uvicorn backend.main:app`)

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```

The frontend will run on `http://localhost:5173` (or similar) and connect to backend at `http://localhost:8015`.
