# AI Answer Verification — Smart Verification

**Mind Masters AI Solutions Pvt. Ltd.** — *Verify Before You Trust.*

Paste text, upload a PDF or a screenshot (or combine them) and click **Generate Verification**. The app extracts the
content, has an AI model identify claims, key details and warning signs, checks claims against any other material you
submitted, and produces a results page and a client-ready **PDF report**. Results are saved to each user's private history
in Supabase (Row Level Security). Earlier evidence-based verifications remain viewable.

| Part | Stack | Port |
|---|---|---|
| Frontend | React 18 · TypeScript · Vite · Tailwind CSS · Lucide | 5173 |
| Backend | Python 3.11 · FastAPI · Pydantic v2 · pypdf · pypdfium2 · Pillow · ReportLab | 8001 |
| Data | Supabase PostgreSQL + Auth (RLS); table `verifications` (no schema change needed for v2) | — |
| AI | OpenRouter, server-side only, model from `OPENROUTER_DEFAULT_MODEL` (tested: `openai/gpt-4o-mini`) | — |

## How a Smart Verification works

| Input | Handling | Limits |
|---|---|---|
| Text | Sent to the model as typed | 20,000 characters |
| Text-based PDF | Text extracted on the server (pypdf) | 10 MB, first 30 pages, 30,000 characters |
| Scanned / image-only PDF | First 3 pages rendered (pdfium) and read by the vision model; stated as a limitation | 3 pages |
| PNG / JPG / WebP | Validated, downscaled to ≤ 2000 px, read by the vision model | 5 MB each |

Up to 3 files per verification; file types are checked by content, not just extension. **Uploaded files and extracted
document text are not stored** — only file names, sizes, page counts and the analysis.

1. **Analysis** (one model call): summary, overall assessment, key findings, warning signs, claims, next steps.
2. **Cross-check** (second call, only when ≥ 2 readable inputs): each claim is checked against the *other* inputs.
3. **Safeguards** (deterministic, not AI):
   - *Supported/Contradicted by Evidence* only when the quoted evidence is found verbatim (or near-verbatim) in a
     **different** submitted input; otherwise it is downgraded and the reason is shown.
   - Claims about payments, bank details, codes or deadlines are always *Requires Human Review*.
   - Contact details (emails, links, domains, phone numbers, amounts, dates) are pattern-matched and shown separately.
   - No accuracy percentages, no invented citations, no "fraud" verdicts; a warning-sign level is shown instead.
4. **Failures are explicit:** if OpenRouter fails, the user sees the error and nothing is saved — there is no offline fallback.
   If the configured model cannot read images, image uploads are rejected with an explanation.

**No external search service is integrated.** Claims that cannot be checked against the submitted material are labelled
*Not Independently Verified*. Adding a search API (e.g. a web-search provider) would be required for independent checking.

Assessments: **Supported by Evidence · Contradicted by Evidence · Not Independently Verified · Requires Human Review.**
Reviewers can override any assessment with a note; overrides appear in all reports.

## Quick start (Windows PowerShell)

### 1. Backend

```powershell
cd ai-answer-verification\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env      # then edit .env (leave keys blank for offline mode)
uvicorn app.main:app --reload --port 8001
```

API docs: http://localhost:8001/docs

### 2. Frontend (in a second terminal)

```powershell
cd ai-answer-verification\frontend
npm install
Copy-Item .env.example .env      # optional
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to the backend on port 8001.

## Configuration (`backend/.env`)

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | Required for Smart Verification. |
| `OPENROUTER_DEFAULT_MODEL` | Model used for every verification. Must accept images for screenshots/scanned PDFs (e.g. `openai/gpt-4o-mini`, `google/gemma-3-27b-it`). `/api/health` reports `vision_supported`. |
| `OPENROUTER_TIMEOUT_SECONDS` / `OPENROUTER_MAX_RETRIES` | Request timeout and the number of retries on 429/5xx. |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` | Enables Supabase storage and sign-in. Leave blank for local JSON storage with no authentication. |
| `CORS_ORIGINS` | Allowed browser origins. |

**Secrets never reach the browser.** The frontend holds no keys: sign-in, AI calls and database access all go through the backend. The backend sends Supabase requests using the signed-in user's JWT, so Row Level Security is enforced.

### Supabase setup

1. Create a Supabase project. Then open **SQL editor** and run `backend/supabase/schema.sql`. It creates the `verifications` table and RLS policies that restrict each user to their own rows.
2. Under **Authentication → Providers**, enable Email.
3. Put the project URL and anon key in `backend/.env`, then restart the backend. The UI now shows a sign-in screen.

## Tests

```powershell
cd backend;  .\.venv\Scripts\python -m pytest     # 38 mocked tests (fake AI, local storage, real generated PDFs/images)
cd frontend; npm test; npm run build

# LIVE tests (real OpenRouter + Supabase; backend running on 8001)
cd backend
.\.venv\Scripts\python scripts\make_live_samples.py live-samples
.\.venv\Scripts\python scripts\live_smart_test.py live-samples live-out      # Smart Verification
.\.venv\Scripts\python scripts\live_integration_test.py --live-ai --cleanup  # auth, CRUD and RLS isolation
```
The live scripts create throwaway users (`mm-av-*@example.com`); delete them in Supabase → Authentication → Users.

## API overview

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | AI mode, storage, auth, models |
| POST | `/api/smart-verifications` | Smart Verification (multipart: `text`, `files[]`) |
| POST | `/api/verifications` | Earlier evidence-based verification (JSON; kept for compatibility) |
| GET | `/api/verifications` · `/api/verifications/{id}` | History list and detail |
| PUT / DELETE | `/api/verifications/{id}/claims/{claim_id}/review` | Set or clear a human review |
| GET | `/api/verifications/{id}/report?format=pdf\|markdown\|json` | Download a report (PDF for Smart Verifications) |
| GET | `/api/review-queue` · `/api/stats` | Review queue and dashboard analytics |
| POST | `/api/auth/login` · `/api/auth/signup` · `/api/auth/refresh` | Supabase auth, proxied through the backend |

## Earlier evidence-based records

Records created before Smart Verification open in their original view, with their reliability score
(`100 × (supported + 0.5 × uncertain) / total`) and Markdown/JSON exports.
