# AtomQuest Submission Checklist

## Live Demo

- Backend health check: `/health`
- Frontend environment variable: `VITE_API_URL=<backend-url>`
- Demo role switcher visible on landing page

## Required Demo Journeys

- Employee: edit seeded goals, keep total weightage at 100%, submit for approval.
- Manager: review approval queue, edit target or weightage inline, approve and lock.
- Employee: enter Q1 actual achievement after approval.
- Manager: complete Q1 check-in comment.
- Admin: view completion dashboard, audit trail, unlock an exception, download CSV report.

## Credentials

- Employee: `employee@atomberg.demo`
- Manager: `manager@atomberg.demo`
- Admin: `admin@atomberg.demo`

## Bonus Features (Demo / MVP)

- Microsoft Entra ID: `POST /auth/entra/sso`, `GET /auth/entra/status`, `GET /org/hierarchy`
- Email & Teams: notification queue at `GET /admin/notifications` (deep links on each row)
- Escalations: `GET /admin/escalations`, `POST /admin/escalations/run`
- Advanced analytics: QoQ trends, department heatmap, UoM chart on admin dashboard

## Submission Assets

- Live portal URL
- Source repository URL
- Architecture PDF generated from `ONE_PAGER.md`
- Demo credentials

## Final Smoke Tests

- `python -m py_compile backend/main.py`
- `cd frontend && npm run build`
- Backend workflow smoke test through FastAPI TestClient or live browser
