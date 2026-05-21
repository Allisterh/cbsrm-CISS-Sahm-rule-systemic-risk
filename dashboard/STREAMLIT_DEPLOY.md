# Deploy the CBSRM Dashboard to Streamlit Community Cloud

**Cost:** $0. No credit card. Public URL you can paste into LinkedIn / cold emails / the CBSRM README.
**Time:** ~10 minutes.

The dashboard at `dashboard/streamlit_app.py` already runs locally (see `dashboard/README.md`). This guide gets it onto a public URL like `https://cbsrm.streamlit.app/` (the exact subdomain is chosen during deploy).

---

## Step 1 — Verify it runs locally first

```bash
cd cbsrm
pip install -e ".[all]"
pip install streamlit pandas numpy requests
export FRED_API_KEY=your_fred_key
streamlit run dashboard/streamlit_app.py
```

Open http://localhost:8501. All 5 panels should render. Take note of the wall time — first-load is ~15-20 s (the GARCH-DCC Monte Carlo + 3 FRED + 3 ECB SDMX calls). If anything errors, fix it locally before deploying — deploy logs are harder to debug.

---

## Step 2 — Push to GitHub (you've already done this)

The dashboard ships in `cbsrm/dashboard/` on the `main` branch of github.com/pravo123/cbsrm. Streamlit Cloud pulls directly from the public repo, so this step is already done.

---

## Step 3 — Create the Streamlit Community Cloud app

1. Go to https://share.streamlit.io and sign in with GitHub (uses OAuth; no separate password)
2. Click **"New app"** in the top-right
3. Fill in:
   - Repository: `pravo123/cbsrm`
   - Branch: `main`
   - Main file path: `dashboard/streamlit_app.py`
   - App URL: `cbsrm` (yields `cbsrm.streamlit.app` — claim it before someone else does)
4. Click **Advanced settings**:
   - Python version: 3.11
   - Secrets (TOML format):
     ```toml
     FRED_API_KEY = "448c6243ab8a67cd5747c69f5b96c9f3"
     ```
   (Streamlit Cloud injects these as `os.environ` at runtime — no `.env` needed)
5. Click **Deploy**

The first deploy takes ~3-5 minutes (pip install + initial page render). Watch the build log for any pip-resolution errors.

---

## Step 4 — Pin the requirements

Streamlit Cloud reads `requirements.txt` from the repo root. The dashboard's `dashboard/requirements.txt` is for local use; Streamlit Cloud needs root-level `requirements.txt` containing:

```
streamlit>=1.35.0
pandas>=2.0
numpy>=1.24
requests>=2.31
-e .
```

If a root `requirements.txt` already exists, append the `-e .` line so Streamlit Cloud installs the cbsrm package itself.

---

## Step 5 — Add a disclaimer block to dashboard README

Open `dashboard/README.md` and append:

```markdown
## Hosted demo

A free public-cloud-hosted version of this dashboard is at:

  https://cbsrm.streamlit.app/   (replace with your actual Streamlit URL)

The hosted version uses the same code as the local one but with a single
FRED API key (rate-limited by FRED's free tier). For your own production
use, deploy a private copy with your own FRED key — instructions in
`STREAMLIT_DEPLOY.md`.
```

Commit + push. Streamlit Cloud auto-redeploys on push to `main`.

---

## Step 6 — Use the URL

Once the deploy is green, paste the URL into:

- **The CBSRM repo README** — add to the "Quick start" section: "Try it without installing → cbsrm.streamlit.app"
- **LinkedIn Draft 7** (the dashboard release post) — replace the placeholder "Try it yourself"
- **The cold-email templates** in `COLD_EMAILS.md` — adds another concrete artifact link
- **Hacker News submission** (`SHOW_HN_POST.md`) — strongly recommended for the front-page filter
- **Your GitHub profile README**

A hosted demo URL is the single highest-converting artifact for cold-outreach because it lets the recipient evaluate the work in 30 seconds without any install friction.

---

## Operational notes

- **Streamlit Cloud free tier limits:** 1 GB RAM, 1 vCPU per app, public-only (any visitor can view your app — that's the point for the demo, but be aware your FRED key would be exposed if you logged it). The free tier sleeps after 7 days of no activity; first visitor wakes it up (~10 sec).
- **FRED rate limit:** the free FRED tier is 120 requests/minute. The dashboard caches each indicator for 1 hour (`@st.cache_data(ttl=3600)`), so for any reasonable visitor traffic you should stay well within limits.
- **Logs:** Streamlit Cloud's "Manage app" panel has live tail of logs. If a panel breaks, that's where you see the traceback.
- **Auto-deploys:** every push to `main` triggers a re-deploy. The dashboard restarts in ~30 sec; visitors see a brief loading state.

---

## If anything goes wrong

- **Pip resolution error:** add the failing package to `requirements.txt` with an explicit version pin
- **FRED 403 / no data:** double-check the secret is set in Streamlit Cloud's settings AND named `FRED_API_KEY` exactly
- **App crash on first load:** view the build log, check for import errors (often: a module that imports correctly locally because of editable-install path resolution but breaks on Streamlit Cloud)
- **Fallback:** if Streamlit Cloud doesn't work, the same app runs identically on Hugging Face Spaces (free, similar limits, GitHub deploy support). The deploy guide is essentially the same — just point at a new Space instead.
