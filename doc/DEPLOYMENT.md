# AEGIS — Deployment Plan (Google Cloud Edition)

> Replaces the original Railway/Render plan in `PROJECT_PLAN.md` / `ARCHITECTURE.md`.
> Rationale: this is a Google hackathon — deploying on Google's own stack (Cloud Run + Firebase)
> is both on-brand for judges and removes a whole class of problems (CORS, cold-start
> unpredictability, mismatched hosting providers) the original plan had to work around.

---

## 1. Stack Mapping (Old → New)

| Layer | Original Plan | New Plan (Google) |
|---|---|---|
| Backend hosting | Railway / Render | **Cloud Run** (containerized FastAPI) |
| Frontend hosting | Vercel / Cloudflare Pages | **Firebase Hosting** (serves the React build) |
| Container build | — | **Cloud Build** (or local `gcloud builds submit`) |
| Image storage | — | **Artifact Registry** |
| Secrets (API keys) | `.env` file | **Secret Manager** |
| Keep-alive ping | generic cron | **Cloud Scheduler** |
| Logs / monitoring | — | **Cloud Logging** (built in, no setup) |
| Backup tunnel | ngrok | **Cloud Run itself** (redeploy is fast enough to skip ngrok) or ngrok as last resort |
| Demo backup | YouTube (unlisted) | unchanged — keep this |

Key win: **Firebase Hosting can rewrite `/api/**` to your Cloud Run service.** That means the frontend and backend appear to live on the *same domain* from the browser's point of view — so you can largely skip CORS configuration entirely. This is the single biggest simplification versus the original plan.

---

## 2. Architecture After the Change

```
Browser
  │
  ▼
Firebase Hosting  (your-project.web.app)
  ├── /            → React build (static files)
  ├── /api/**      → rewritten to → Cloud Run service (FastAPI backend)
  └── /events (SSE)→ rewritten to → Cloud Run service (same origin, no CORS needed)
```

Cloud Run supports streamed HTTP responses, so Server-Sent Events work without changes to your `/api/events` endpoint — just make sure FastAPI returns a `StreamingResponse` with `media_type="text/event-stream"` as originally planned.

---

## 3. One-Time Setup (do this in the first 30 minutes, alongside the API spike)

```bash
# Install & auth
gcloud components install beta   # if needed
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudscheduler.googleapis.com

# Firebase
npm install -g firebase-tools
firebase login
firebase init hosting   # select existing GCP project, set public dir to your React build output (e.g. "build" or "dist")
```

Store the Antigravity API key as a secret instead of a plain env var (safer, and still fast):

```bash
echo -n "YOUR_ANTIGRAVITY_API_KEY" | gcloud secrets create ANTIGRAVITY_API_KEY --data-file=-
```

---

## 4. Backend: Dockerfile for Cloud Run

Cloud Run needs a container image. Minimal Dockerfile for the FastAPI backend:

```dockerfile
# aegis/backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

> Cloud Run injects `PORT` automatically (defaults to 8080) — make sure `main.py` reads `PORT` from the environment rather than hardcoding 8000, since the original plan assumed `PORT=8000`.

---

## 5. Backend Deployment Commands

```bash
cd aegis/backend

# Build & push image, then deploy in one step
gcloud run deploy aegis-backend \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars ANTIGRAVITY_API_BASE_URL=https://<base-url>,CORS_ORIGINS=* \
  --set-secrets ANTIGRAVITY_API_KEY=ANTIGRAVITY_API_KEY:latest \
  --min-instances=1 \
  --timeout=300
```

Notes:
- `--source .` tells Cloud Run to build the container for you via Cloud Build — no manual Docker build needed, good for a 5-hour timeline.
- `--min-instances=1` keeps one instance warm during the judging window (avoids cold-start lag on the first "Trigger Incident" click). This costs a small amount — fine to only enable ~30 minutes before your demo slot, then scale back down (`--min-instances=0`) after.
- `--timeout=300` is plenty since `RISKS.md` already caps incident duration at 2 minutes (120s).
- Note the URL it prints (`https://aegis-backend-xxxxx-uc.a.run.app`) — you'll need it for the Firebase rewrite.

---

## 6. Frontend (React) Deployment

```bash
cd aegis/frontend
npm run build
```

`firebase.json` — this is what makes `/api/**` transparently proxy to Cloud Run (no CORS needed):

```json
{
  "hosting": {
    "public": "build",
    "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
    "rewrites": [
      {
        "source": "/api/**",
        "run": {
          "serviceId": "aegis-backend",
          "region": "us-central1"
        }
      },
      {
        "source": "**",
        "destination": "/index.html"
      }
    ]
  }
}
```

Deploy:

```bash
firebase deploy --only hosting
```

Your app is now live at `https://your-project.web.app`, with the React app served from Firebase and every `/api/*` call (including the SSE stream) silently forwarded to Cloud Run.

> Since React's `EventSource('/api/events')` now hits the same origin, no CORS headers are needed at all — you can leave `CORS_ORIGINS=*` on the backend purely as a safety net for local dev.

---

## 7. Keep-Alive (Optional, Cloud Scheduler)

If you don't want to pay for `--min-instances=1` the whole event, use Cloud Scheduler to ping the health endpoint every 5 minutes only during the demo window instead:

```bash
gcloud scheduler jobs create http aegis-keepalive \
  --schedule="*/5 * * * *" \
  --uri="https://aegis-backend-xxxxx-uc.a.run.app/api/health" \
  --http-method=GET \
  --location=us-central1
```

Delete the job after judging (`gcloud scheduler jobs delete aegis-keepalive`) so it doesn't run forever.

---

## 8. Three Layers of Redundancy (Updated)

| Layer | What |
|---|---|
| **Primary** | Firebase Hosting (frontend) + Cloud Run (backend), `--min-instances=1` during the judging slot |
| **Backup 1** | Redeploy is a single `gcloud run deploy --source .` command — often faster to just re-deploy than to spin up ngrok. Keep ngrok as a fallback only if Cloud Run itself is down (rare) |
| **Backup 2** | Pre-recorded 2-minute demo video, uploaded to YouTube (unlisted) — unchanged from the original plan, prepare regardless of hosting status |

---

## 9. Updated Deployment Checklist

- [ ] `gcloud` + `firebase` CLIs authenticated to the hackathon's GCP project
- [ ] Required APIs enabled (Cloud Run, Cloud Build, Artifact Registry, Secret Manager, Cloud Scheduler)
- [ ] `ANTIGRAVITY_API_KEY` stored in Secret Manager, not committed to git
- [ ] `Dockerfile` present in `aegis/backend/`, reads `PORT` from env
- [ ] Backend deployed to Cloud Run, `/api/health` returns 200
- [ ] React app built (`npm run build`) and deployed to Firebase Hosting
- [ ] `firebase.json` rewrites confirmed working (`/api/**` → Cloud Run; SSE stream visibly updating in browser dev tools)
- [ ] `--min-instances=1` set ~30 min before demo slot; removed after
- [ ] `.gitignore` excludes `.env`, `__pycache__`, `state_*.json`, `node_modules`, `build/`
- [ ] README updated with: live Firebase Hosting URL, architecture diagram, setup instructions, demo video link
- [ ] Pre-recorded demo video uploaded (unlisted) regardless of live status

---

## 10. Where This Slots Into the 5-Hour Timeline

Same checkpoint structure as before, just swap the tools:

| Time | Original | New |
|---|---|---|
| 3:30 | Deploy to Railway/Render + Vercel | Deploy to Cloud Run + Firebase Hosting |
| 3:30 (if fails) | ngrok tunnel | Re-run `gcloud run deploy` (usually faster than standing up ngrok) |
| 4:00 | Record demo video regardless | unchanged |
