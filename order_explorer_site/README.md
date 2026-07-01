# Order Explorer Site

## Project Structure
- `backend/`: FastAPI application
- `frontend/`: React Vite application

## Prerequisites
- Python 3.9+
- Node.js 16+

## Setup & Run

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
