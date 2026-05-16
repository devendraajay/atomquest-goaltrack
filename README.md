# AtomQuest GoalTrack Portal

A 24-hour hackathon build for AtomQuest Hackathon 2026: an in-house goal setting and tracking portal for employees, L1 managers, and Admin/HR.

## Demo Credentials

The app uses demo role switching through seeded users:

- Employee: `employee@atomberg.demo`
- Manager: `manager@atomberg.demo`
- Admin/HR: `admin@atomberg.demo`

## Core Features

- Employee goal sheet creation with thrust area, UoM, targets, and weightage.
- Server-side validations: total weightage equals 100%, minimum 10% per goal, maximum 8 goals.
- L1 manager approval workflow with inline target and weightage edits.
- Goal locking after approval and Admin unlock exception handling.
- Shared departmental KPI push to multiple employees.
- Quarterly achievement tracking with computed progress scores.
- Manager check-in comments and completion tracking.
- Admin dashboard, analytics charts, audit trail, and CSV achievement export.

## Tech Stack

- Frontend: React, TypeScript, Vite, Recharts.
- Backend: FastAPI, SQLAlchemy, Pydantic.
- Database: PostgreSQL in production, SQLite default for local development.
- Hosting: Render/Railway for API and database, Vercel for frontend.

## Local Development

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Set `frontend/.env`:

```bash
VITE_API_URL=http://localhost:8000
```

## Deployment

1. Deploy `backend` to Render using `backend/render.yaml` or as a Docker web service.
2. Attach a free PostgreSQL database and set `DATABASE_URL`.
3. Deploy `frontend` to Vercel.
4. Set `VITE_API_URL` in Vercel to the live backend URL.
5. Verify `/health`, role switching, submission, approval, check-in, dashboard, and CSV export.
