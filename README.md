# Soccer Tactics Article Generator

An end-to-end pipeline that:

- Crawls tactical content from [thefalse9.com](https://thefalse9.com)
- Builds a Retrieval-Augmented Generation (RAG) index with Gemini embeddings
- Exposes a FastAPI backend for generating articles
- Ships with a lightweight browser UI (`app/web/index.html`)

## Requirements

- Python 3.11+ (3.11.4+ recommended)
- A Google Gemini API key (`GEMINI_API_KEY` or `GOOGLE_API_KEY`)
- Windows PowerShell commands in the examples; adapt for other shells as needed

## Setup

```powershell
git clone https://github.com/ritesh-gogineni/soccer-tactics-guide.git
cd soccer-tactics-guide
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a `.env` file (or export env vars) with your Gemini key:

```dotenv
GEMINI_API_KEY=your_key_here
```

## Configuration

`config.json` controls crawl behavior:

```json
{
  "crawllevel": "minimal",
  "max_articles_per_run": 15
}
```

- `crawllevel`: `"minimal"` starts from the Beginners category; `"full"` starts from the homepage.
- `max_articles_per_run`: cap on newly captured articles per crawl invocation.

## Crawling & Indexing Workflow

The crawler is a standalone script that should be run whenever you need to refresh the RAG data.

```powershell
python crawl_thefalse9.py
```

What it does:

1. Loads `thefalse9_corpus.json` (if present) to avoid re-processing URLs.
2. Crawls up to `max_articles_per_run` new articles (full text, not snippets).
3. Appends new content to `thefalse9_corpus.json`.
4. Generates embeddings for the new articles only and appends them to `app/thefalse9_index.json`.

> Tip: delete `thefalse9_corpus.json` and `app/thefalse9_index.json` to rebuild everything from scratch.

## Running the FastAPI Backend

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Endpoints:

- `GET /` – health check.
- `POST /generate` – accepts a JSON body defined in `app/main.py` and returns an article generated via Gemini plus retrieved context.

## Loading the UI

The UI is a static HTML file that directly POSTs to `http://127.0.0.1:8000/generate`.

From Windows PowerShell:

```powershell
start "" "app\web\index.html"
```

Or serve it:

```powershell
cd app\web
python -m http.server 8080
# browse to http://localhost:8080
```

Fill the form, click **Generate**, and the backend response will be displayed on the page.

## Data Artifacts

- `thefalse9_corpus.json`: repository of crawled articles (title, URL, full text).
- `app/thefalse9_index.json`: embedding index consumed by `app/rag.py`.

Keep both files under version control if you need deterministic runs; otherwise you can treat them as generated artifacts.

## Troubleshooting

- **Crawler stores short snippets** – ensure you're on the latest code (`extract_article_text` now targets real content wrappers). Delete the corpus/index and rerun the crawler if needed.
- **`405 Method Not Allowed` on `/generate`** – the endpoint is POST-only; hit it via the UI or a POST tool like curl/Postman.
- **UI doesn't open** – use `start "" "app\web\index.html"` or serve via `python -m http.server`.
- **Gemini errors** – verify `.env` is loaded and the API key has embedding access.

## Project Structure

```
app/
  llmclient.py         # Gemini-based article generation utility
  main.py              # FastAPI entry point
  rag.py               # Retrieval helpers + incremental index builder
  prompts.py           # System + user templates
  web/index.html       # Browser UI
crawl_thefalse9.py     # Crawler + indexing orchestration
config.json            # Crawl configuration
requirements.txt       # Python dependencies
thefalse9_corpus.json  # (generated) Crawled dataset
```

## Contributing

Pull requests and issues are welcome. Please run the crawler locally and confirm `uvicorn app.main:app --reload` works before submitting changes.
