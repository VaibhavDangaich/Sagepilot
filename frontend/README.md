# Order Supervisor — Frontend

Next.js (App Router) + Tailwind UI for the Order Supervisor POC. See the
[repo root README](../README.md) for full setup instructions (backend, Temporal, DB) and
[`../ARCHITECTURE.md`](../ARCHITECTURE.md) for the design write-up.

```bash
pnpm install
pnpm dev
```

Talks to the FastAPI backend at `NEXT_PUBLIC_API_BASE_URL` (see `.env.local`, defaults
to `http://localhost:8000`).
