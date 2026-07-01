# ContestRagIQ — RAG Document Chat Application

Upload PDFs and chat with them using Google Gemini, grounded in semantic search
over Qdrant vector embeddings. JWT-authenticated, multi-user, source-cited,
deployable to Render (backend) + Vercel (frontend) + Qdrant Cloud (vectors).

---

## Tech Stack

| Layer          | Choice                                              |
| -------------- | --------------------------------------------------- |
| Backend        | FastAPI (async), Pydantic v2, SQLAlchemy 2 async    |
| Auth           | JWT (access 30min + refresh 7d, httpOnly cookie)    |
| OAuth          | Google Sign-In via Authlib + OpenID Connect          |
| Relational DB  | PostgreSQL 15 (asyncpg)                             |
| Vector DB      | Qdrant Cloud (cosine, 768-dim)                      |
| LLM            | Google Gemini (`gemini-flash-latest`)                |
| Embeddings     | Google `gemini-embedding-001` (768 dims)            |
| PDF parsing    | PyMuPDF (fitz)                                      |
| Migrations     | Alembic                                             |
| Frontend       | React 18 + Vite, Tailwind CSS, React Router v6      |
| HTTP client    | Axios with silent-refresh interceptor               |

---

## Repository Layout

```
root/
├── scratch/                          # Ad-hoc test scripts
├── backend/
│   ├── main.py                       # FastAPI app entry
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── .env.example
│   ├── .python-version
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       ├── 0001_initial.py
│   │       └── 0002_add_google_oauth_fields.py
│   └── app/
│       ├── __init__.py
│       ├── config.py                 # Pydantic-settings
│       ├── database.py               # async engine + session
│       ├── models/models.py          # User, Document, ChatMessage
│       ├── schemas/                  # auth, documents, chat
│       ├── auth/                     # router, service, dependencies
│       ├── documents/                # router, service, ingestion
│       ├── chat/                     # router, RAG service
│       ├── vector/qdrant_client.py
│       ├── services/google_auth.py   # Authlib OAuth client + JWKS verify
│       └── utils/                    # security, errors
└── frontend/
    ├── vercel.json
    ├── vite.config.js
    ├── package.json
    ├── postcss.config.js
    ├── tailwind.config.js
    ├── .env.example
    ├── public/
    │   ├── favicon.png
    │   └── logo.png
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── index.css
        ├── api/axios.js              # Axios + silent-refresh interceptor
        ├── context/AuthContext.jsx
        ├── pages/
        │   ├── Login.jsx
        │   ├── Register.jsx
        │   ├── Dashboard.jsx
        │   ├── Chat.jsx
        │   └── AuthCallback.jsx
        └── components/
            ├── ProtectedRoute.jsx
            ├── UploadZone.jsx
            ├── DocumentCard.jsx
            ├── MessageBubble.jsx
            ├── MarkdownRenderer.jsx
            ├── SourceBadge.jsx
            └── CommandMenu.jsx
```

---

## Frontend Features

- **Dark/light theme** — persisted in `localStorage`, no flash on reload (inline script)
- **Command palette** (`Ctrl+K` / `Cmd+K`) — navigate documents, upload, sign out
- **Upload progress bar** — real-time percentage during PDF upload
- **Optimistic chat updates** — user message appears instantly, replaced on response
- **Auto-polling** — dashboard refreshes every 3s while documents are processing
- **Custom Markdown renderer** — handles code blocks, lists, headings, `[Page N]` citations
- **Demo account shortcut** — one-click fill on login page

---

## Local Development

### Prerequisites
- Python 3.10+
- Node 18+
- PostgreSQL 15 running locally (or use Docker)
- A Qdrant instance (local Docker or Qdrant Cloud)
- A Google Gemini API key ([get one here](https://aistudio.google.com/app/apikey))
- A Google OAuth client ID + secret ([Google Cloud Console](https://console.cloud.google.com/apis/credentials))

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your values (all variables below):
```

**Required env vars:**

| Variable                   | Description                                              |
| -------------------------- | -------------------------------------------------------- |
| `DATABASE_URL`             | `postgresql+asyncpg://postgres:postgres@localhost:5432/ragchat` |
| `QDRANT_URL`               | `http://localhost:6333` or Qdrant Cloud URL              |
| `QDRANT_API_KEY`           | (empty if local Qdrant)                                  |
| `GEMINI_API_KEY`           | from Google AI Studio                                    |
| `JWT_SECRET`               | 32+ random characters                                    |
| `GOOGLE_CLIENT_ID`         | from Google Cloud Console                                |
| `GOOGLE_CLIENT_SECRET`     | from Google Cloud Console                                |
| `FRONTEND_URL`             | `http://localhost:5173`                                  |
| `BACKEND_URL`              | `http://localhost:8000`                                  |

**Optional env vars with defaults:**

| Variable                   | Default                       | Description                        |
| -------------------------- | ----------------------------- | ---------------------------------- |
| `QDRANT_COLLECTION`        | `document_chunks`             | Qdrant collection name             |
| `GEMINI_MODEL`             | `gemini-flash-latest`         | Gemini model for answers           |
| `GEMINI_EMBEDDING_MODEL`   | `gemini-embedding-001`        | Model for embeddings               |
| `EMBEDDING_DIMENSIONS`     | `768`                         | Embedding vector dimensions        |
| `CHUNK_MAX_TOKENS`         | `500`                         | Max tokens per chunk               |
| `CHUNK_OVERLAP_TOKENS`     | `50`                          | Overlap between chunks             |
| `RAG_TOP_K`                | `5`                           | Number of chunks to retrieve       |
| `RAG_HISTORY_MESSAGES`     | `6`                           | Chat history turns for context     |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30`                       | Access token TTL                   |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7`                          | Refresh token TTL                  |
| `REFRESH_COOKIE_NAME`      | `refresh_token`               | Cookie name for refresh token      |
| `ALLOWED_ORIGINS`          | `http://localhost:5173`       | Comma-separated CORS origins       |
| `COOKIE_SECURE`            | `false`                       | Set `true` in production           |
| `COOKIE_SAMESITE`          | `lax`                         | `strict` in production             |
| `ENVIRONMENT`              | `development`                 | Controls debug/echo settings       |

```bash
# Create the database (one-time):
createdb ragchat

# Run migrations:
alembic upgrade head

# Start the API:
uvicorn main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` for interactive Swagger UI.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env
# VITE_API_URL=http://localhost:8000

npm run dev
```

Visit `http://localhost:5173`, register an account, upload a PDF, and start chatting.

### 3. Google OAuth (local)

1. In Google Cloud Console, create an OAuth 2.0 Web Client.
2. Add `http://localhost:8000/auth/google/callback` as an **Authorized redirect URI**.
3. Add `http://localhost:5173` as an **Authorized JavaScript origin**.
4. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`.

### 4. Local Qdrant (optional, via Docker)

```bash
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

---

## API Reference

### Auth
| Method | Endpoint                | Description                                  |
| ------ | ----------------------- | -------------------------------------------- |
| POST   | `/auth/register`        | Register; returns access token + sets cookie |
| POST   | `/auth/login`           | Login; returns access token + sets cookie    |
| POST   | `/auth/refresh`         | Reads cookie, returns new access token       |
| POST   | `/auth/logout`          | Clears refresh cookie                        |
| GET    | `/auth/me`              | Current user profile (id, email, name, picture, etc.) |
| GET    | `/auth/google/login`    | Redirect to Google OAuth consent screen      |
| GET    | `/auth/google/callback` | OAuth callback — sets cookie, redirects to frontend |

### Documents
| Method | Endpoint                    | Description                                  |
| ------ | --------------------------- | -------------------------------------------- |
| POST   | `/documents/upload`         | Upload PDF (max 25MB), triggers ingestion    |
| GET    | `/documents`                | List current user's documents                |
| GET    | `/documents/{id}`           | Get document metadata + status               |
| DELETE | `/documents/{id}`           | Delete document + vectors + chat history     |

### Chat
| Method | Endpoint                  | Description                                |
| ------ | ------------------------- | ------------------------------------------ |
| POST   | `/chat`                   | Ask a question; returns answer + sources   |
| GET    | `/chat/{document_id}`     | Fetch full chat history for a document     |

### System
| Method | Endpoint                               | Description                            |
| ------ | -------------------------------------- | -------------------------------------- |
| GET    | `/health`                              | `{ "status": "ok" }` — uptime ping     |
| GET    | `/documents/debug/ingestion-error`     | Read last ingestion error (dev only)   |

Errors return `{ "detail": str, "code": "SNAKE_CASE_CODE" }`. Validation errors additionally include an `errors` array.

---

## Deployment

Follow this order strictly.

### Step 1 — Qdrant Cloud
1. Sign up at [cloud.qdrant.io](https://cloud.qdrant.io).
2. Create a free 1GB cluster.
3. Copy the **cluster URL** and **API key**.

### Step 2 — Render PostgreSQL
1. On [render.com](https://render.com), create a new **PostgreSQL** instance (free tier).
2. Copy the **internal DATABASE_URL** (format: `postgresql://user:pass@host:5432/db`).
3. Append `+asyncpg` to make it: `postgresql+asyncpg://user:pass@host:5432/db`.

### Step 3 — Google Cloud OAuth config
1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
2. Create an OAuth 2.0 Web Client if you haven't already.
3. Add `https://<your-app>.onrender.com/auth/google/callback` as an **Authorized redirect URI**.
4. Add `https://<your-vercel-app>.vercel.app` as an **Authorized JavaScript origin**.

### Step 4 — Render FastAPI backend
1. New **Web Service** → connect your repo → **Root Directory: `backend`**.
2. **Runtime:** Python 3.10.
3. **Build Command:** `pip install -r requirements.txt && alembic upgrade head`
4. **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. **Health Check Path:** `/health`
6. Add environment variables:

   | Key                            | Value                                              |
   | ------------------------------ | -------------------------------------------------- |
   | `DATABASE_URL`                 | `postgresql+asyncpg://...` (from Step 2)           |
   | `QDRANT_URL`                   | from Step 1                                        |
   | `QDRANT_API_KEY`               | from Step 1                                        |
   | `GEMINI_API_KEY`               | from Google AI Studio                              |
   | `JWT_SECRET`                   | 32+ random characters                              |
   | `GOOGLE_CLIENT_ID`             | from Google Cloud Console                          |
   | `GOOGLE_CLIENT_SECRET`         | from Google Cloud Console                          |
   | `FRONTEND_URL`                 | `https://<your-app>.vercel.app` (set in Step 5)   |
   | `BACKEND_URL`                  | `https://<your-app>.onrender.com`                  |
   | `JWT_ALGORITHM`                | `HS256`                                            |
   | `ACCESS_TOKEN_EXPIRE_MINUTES`  | `30`                                               |
   | `REFRESH_TOKEN_EXPIRE_DAYS`    | `7`                                                |
   | `ALLOWED_ORIGINS`              | `https://<your-app>.vercel.app` (set in Step 5)   |
   | `COOKIE_SECURE`                | `true`                                             |
   | `COOKIE_SAMESITE`              | `none`                                             |
   | `ENVIRONMENT`                  | `production`                                       |

7. Deploy. Check logs confirm: migrations ran, Qdrant collection created.
8. Hit `https://<your-app>.onrender.com/health` → expect `{"status":"ok"}`.

### Step 5 — Vercel frontend
1. On [vercel.com](https://vercel.com), **New Project** → import your repo.
2. **Root Directory:** `frontend`.
3. **Build Command:** `npm run build`
4. **Output Directory:** `dist`
5. **Environment Variable:** `VITE_API_URL = https://<your-app>.onrender.com`
6. Deploy. Copy the Vercel URL (e.g. `https://doc-chat.vercel.app`).
7. **Go back to Render** and set `ALLOWED_ORIGINS` and `FRONTEND_URL` to the exact
   Vercel URL (with `https://` and **no trailing slash**). Redeploy the backend.
8. **Update Google Cloud Console** — add the Vercel URL to **Authorized JavaScript origins**.

### Step 6 — Uptime cron (mandatory on Render free tier)
Render's free tier sleeps after 15 min of inactivity. Set up a free cron at
[cron-job.org](https://cron-job.org) that pings your backend's `/health`
endpoint every 10 minutes.

---

## Security Notes

- ✅ Access token stored in memory only (React state, never localStorage)
- ✅ Refresh token in `httpOnly`, `Secure`, `SameSite` cookie (lax dev, none prod)
- ✅ CORS allows only explicit origins (no wildcard in production)
- ✅ bcrypt password hashing (cost factor 12)
- ✅ Ownership checks return 403, never 404 (prevents enumeration)
- ✅ Every Qdrant search filters by `document_id` AND `user_id`
- ✅ All secrets via env vars, never committed
- ✅ Axios interceptor queues concurrent 401s — only one refresh call at a time
- ✅ Refresh token rotation — old token invalidated on each refresh
- ✅ Google OAuth CSRF protection via signed state cookie (10 min TTL)
- ✅ Google ID token verified against Google JWKS before user creation

---

## Known Gotchas

1. Render free tier sleeps after 15 min → `/health` cron is mandatory.
2. Render filesystem resets on redeploy → never write PDFs to disk (we don't).
3. Render PostgreSQL free tier expires in 90 days → set a calendar reminder.
4. CORS errors post-deploy → verify `ALLOWED_ORIGINS` matches Vercel domain
   exactly (with `https://`, no trailing slash).
5. Alembic migration failure blocks deploy → test locally first.
6. Qdrant free cluster may throttle when idle → the `/health` ping also helps.
7. `gemini-embedding-001` rate limits → exponential backoff on 429s (built in).
8. Gemini has per-minute rate limits → exponential backoff on 429s (built in).
9. React Router on Vercel returns 404 on refresh without `vercel.json`
   (included in this repo).
10. Never self-host Qdrant on Render — disk wipe on redeploy loses all vectors.
11. Google OAuth redirect URI mismatch → ensure exact match in Cloud Console.

---

## Development Scripts

```bash
# Backend
cd backend
alembic revision --autogenerate -m "describe change"   # new migration
alembic upgrade head                                    # apply
alembic downgrade -1                                    # rollback one

# Frontend
cd frontend
npm run dev      # dev server
npm run build    # production build → dist/
npm run preview  # preview production build
```

---
## System Workflow Overview
![System Overview](flow-diagram.png)
