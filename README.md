# Intelligent Document Processing - Multimodal GenAI

[![CI](https://github.com/Evanguennou29/intelligent-document-processing-multimodal-genai-main/actions/workflows/ci.yml/badge.svg)](https://github.com/Evanguennou29/intelligent-document-processing-multimodal-genai-main/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-pytest-informational)](tests)
[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://VOTRE-APP.streamlit.app)

Turn scans, photos and PDFs into **validated, structured JSON** with one
pipeline that runs either:

* in the cloud -- **Google Vertex AI / Gemini Vision**, or
* fully offline -- **Ollama** with a local vision model,

switchable from the web UI, the CLI or a single environment variable.

> [Version francaise du README](README.fr.md)

---

## Table of contents

- [Why this project](#why-this-project)
- [What's new in v2.0](#whats-new-in-v20)
- [How it works](#how-it-works)
- [Project layout](#project-layout)
- [Requirements](#requirements)
- [Quickstart](#quickstart)
- [Online demo](#online-demo)
- [Configuration](#configuration)
- [Usage](#usage)
- [Supported documents](#supported-documents)
- [Output format](#output-format)
- [Quality: tests, lint, pre-commit](#quality-tests-lint-pre-commit)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Contributing](#contributing)

---

## Why this project

Most OCR demos stop at "here is the raw text". Real document workflows need a
*structured* result: an invoice number, a total, an expiry date, a list of line
items -- and they need to know when the model was unsure.

This project chains three steps and validates the result at every stage:

```
 file  ->  OCR (vision model)  ->  LLM extraction (JSON schema)  ->  Pydantic validation  ->  JSON
```

**Hybrid by design.** National ID cards, medical prescriptions or invoices are
sensitive. The same codebase can send them to Vertex AI for speed and accuracy,
or keep them on your own machine with Ollama. The backend is a runtime choice,
not a fork.

---

## What's new in v2.0

This repository started as an educational project. Version 2.0 is a full
refactor focused on correctness, security and reproducibility.

| Area | Before | Now |
| --- | --- | --- |
| Configuration | `PROJECT_ID = "your_id_project"` hard-coded in `src/config/vertex.py` | everything in `.env`, see `.env.example`; placeholder is detected |
| Duplicated code | `pipeline.py` / `pipeline_with_localversion.py`, `app.py` / `app_final.py`, two extractors | one implementation, one provider abstraction |
| Validation | `validate_document()` returned its argument untouched | real checks: date normalisation, invoice arithmetic, expired documents |
| JSON parsing | naive `` ``` `` split + `json.loads` | fence stripping, brace matching, trailing-comma repair, one repair retry |
| PDF | `pymupdf` in requirements, never used | scanned PDFs are rasterised and processed |
| Caching | none - every run paid the full API cost | content-addressed cache, `IDP_USE_CACHE=false` to disable |
| Routing | `if "id" in filename` matched `video.mp4`, `candidate.png` | word-boundary matching + OCR-text fallback |
| Errors | raw tracebacks, bare `except` | typed exceptions (`OcrError`, `ExtractionError`, ...) with actionable messages |
| Tests | none | 60+ pytest tests, no network required |
| CI / Docker | none | GitHub Actions (3 Python versions) + multi-stage Dockerfile + compose |
| Packaging | loose scripts | installable package with a `idp` CLI entry point |
| Docs | broken markdown code blocks | this README + French version + contributing + security policy |

---

## How it works

```
                   +----------------------+
   upload / CLI -> |      routing         |  filename -> OCR text -> override
                   +----------+-----------+
                              |
                   +----------v-----------+
                   |        OCR           |  Gemini Vision  (cloud)
                   |  (vision model)      |  llama3.2-vision (local)
                   +----------+-----------+
                              |  raw text
                   +----------v-----------+
                   |  LLM extraction      |  JSON-schema-constrained prompt
                   |  gemini-2.5-pro /    |  + code-fence / brace repair
                   |  llama3.2            |  + one repair retry on failure
                   +----------+-----------+
                              |  candidate JSON
                   +----------v-----------+
                   |  Pydantic validation |  schema + business rules
                   |  + normalisation     |  -> warnings list
                   +----------+-----------+
                              |
                            JSON file + _meta
```

Every result carries a `_meta` block: which backend ran, which model, how long
it took, whether it came from cache, and the list of validation warnings.

---

## Project layout

```
.
|-- app/
|   `-- streamlit_app.py         # web interface (hybrid backend switch)
|-- src/
|   `-- idp/                     # the installable package
|       |-- cli.py               # `idp info` / `idp process`
|       |-- config.py            # every setting, from the environment
|       |-- errors.py            # typed exception hierarchy
|       |-- extraction/
|       |   `-- llm_extractor.py # prompts + robust JSON recovery
|       |-- ocr/
|       |   |-- base.py          # OcrEngine contract
|       |   |-- gemini_vision.py # cloud backend (lazy import)
|       |   `-- ollama_vision.py # local backend
|       |-- pdf.py               # PDF -> PNG pages (PyMuPDF)
|       |-- pipeline.py          # orchestration + cache
|       |-- routing.py           # document-type detection
|       |-- schemas.py           # Pydantic models per document type
|       `-- validation.py        # business rules + normalisation
|-- tests/                       # pytest suite, runs offline
|-- notebooks/
|   `-- Evaluation.ipynb         # original evaluation notebook (legacy API)
|-- data/
|   |-- raw/                     # uploaded documents (git-ignored)
|   `-- processed/               # extracted JSON (git-ignored)
|-- .env.example
|-- Dockerfile
|-- docker-compose.yml
|-- pyproject.toml
`-- requirements*.txt
```

---

## Requirements

* Python **3.10+**
* One of the two backends:
  * **Cloud**: a Google Cloud project with the Vertex AI API enabled;
  * **Local**: [Ollama](https://ollama.com/download) installed and running.
* Optional: Docker + Docker Compose for the containerised setup.

---

## Quickstart

### Option A - Docker (fastest path to a running UI)

```bash
git clone https://github.com/Evanguennou29/intelligent-document-processing-multimodal-genai-main.git
cd intelligent-document-processing-multimodal-genai-main

cp .env.example .env          # Windows: copy .env.example .env

docker compose up --build
docker compose exec ollama ollama pull llama3.2-vision
docker compose exec ollama ollama pull llama3.2
```

Open <http://localhost:8501>.

### Option B - Local installation

```bash
git clone https://github.com/Evanguennou29/intelligent-document-processing-multimodal-genai-main.git
cd intelligent-document-processing-multimodal-genai-main
```

Create a virtual environment:

```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

Then pick the configuration that matches your needs:

<details>
<summary><strong>Path 1 - Full hybrid (cloud + local)</strong></summary>

```bash
pip install -r requirements.txt
cp .env.example .env
```

Local backend:

```bash
ollama pull llama3.2-vision
ollama pull llama3.2
ollama serve
```

Cloud backend:

```bash
gcloud auth application-default login
```

then set `VERTEX_PROJECT_ID` in your `.env`.
</details>

<details>
<summary><strong>Path 2 - Cloud only (Vertex AI)</strong></summary>

```bash
pip install -r requirements_vertex.txt
cp .env.example .env
gcloud auth application-default login
```

Enable the Vertex AI API in your Google Cloud console, then set
`VERTEX_PROJECT_ID` and `IDP_PROVIDER=vertex` in `.env`.
</details>

<details>
<summary><strong>Path 3 - Local only (Ollama, offline and free)</strong></summary>

```bash
pip install -r requirements_ollama.txt
cp .env.example .env
ollama pull llama3.2-vision
ollama pull llama3.2
ollama serve
```

Keep `IDP_PROVIDER=ollama` in `.env`. Nothing leaves your machine.
</details>

Launch the interface:

```bash
streamlit run app/streamlit_app.py
```

### For developers

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

---

## Online demo

A public demo is hosted on Streamlit Community Cloud:

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://VOTRE-APP.streamlit.app)

> Replace `VOTRE-APP` with your deployed application URL.

### Demo limits

To protect your API budget, the public demo enforces two quotas:

| Quota | Default |
| --- | --- |
| Documents per visitor | 3 |
| Documents per month | 50 |

Both are configurable through the application secrets
(`DEMO_PER_USER_LIMIT`, `DEMO_MONTHLY_LIMIT`).

### Deploying your own demo

1. Create a Google Cloud **service account** with the Vertex AI User role and
   download its JSON key.
2. On [share.streamlit.io](https://share.streamlit.io), click **New app**,
   select this repository and the entry point `app/streamlit_app.py`.
3. In **Settings > Secrets**, paste the keys from
   [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example) --
   especially `VERTEX_PROJECT_ID` and `GCP_SERVICE_ACCOUNT_JSON`. Secrets are
   **never committed** to the repository.
4. The hosted demo runs on **Vertex AI** (the local Ollama backend is not
   available in the cloud). Adjust the quota values as you see fit.

---

## Configuration

Everything is read from the environment, and `.env` is loaded automatically.
**No secret is ever hard-coded.**

| Variable | Default | Description |
| --- | --- | --- |
| `IDP_PROVIDER` | `ollama` | Default backend: `vertex` or `ollama` |
| `VERTEX_PROJECT_ID` | *(empty)* | Google Cloud project id (required for `vertex`) |
| `VERTEX_LOCATION` | `us-central1` | Vertex AI region |
| `VERTEX_MODEL` | `gemini-2.5-pro` | Gemini model used for OCR and extraction |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama endpoint |
| `OLLAMA_VISION_MODEL` | `llama3.2-vision` | Vision model used for OCR |
| `OLLAMA_TEXT_MODEL` | `llama3.2` | Text model used for extraction |
| `OLLAMA_TIMEOUT` | `180` | Request timeout, in seconds |
| `OLLAMA_MAX_IMAGE_SIDE` | `1024` | Images are downscaled to this long side |
| `IDP_MAX_RETRIES` | `2` | Attempts before giving up |
| `IDP_RETRY_BACKOFF` | `1.5` | Seconds between attempts (multiplied by the attempt number) |
| `IDP_USE_CACHE` | `true` | Reuse previous results for identical files |
| `IDP_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `IDP_RAW_DIR` | `data/raw` | Where uploaded documents are stored |
| `IDP_PROCESSED_DIR` | `data/processed` | Where JSON results are written |
| `IDP_CACHE_DIR` | `.cache/idp` | Cache and rasterised PDF pages |
| `IDP_MAX_UPLOAD_MB` | `25` | UI upload limit |
| `IDP_PDF_MAX_PAGES` | `1` | Pages processed per PDF |
| `IDP_PDF_DPI` | `200` | Rasterisation resolution |

---

## Usage

### Web interface

```bash
streamlit run app/streamlit_app.py
```

The sidebar shows the live status of both engines, lets you pick the backend,
force a document type, and toggle the cache. You can drop several files at once
and download each result as JSON (plus a CSV of invoice line items).

### Command line

```bash
# Inspect the resolved configuration and engine health
python -m idp info

# Process a single file
python -m idp process scan.png --provider vertex

# Process a whole folder with the local backend, without the cache
python -m idp process ./scans -o ./out -p ollama --no-cache

# Force the document type and print the JSON
python -m idp process facture.pdf -t invoice --print
```

After `pip install -e .` the shorter `idp` command is available.

### Python API

```python
from idp import Pipeline

pipeline = Pipeline(provider="ollama")
result = pipeline.process("scan.png")

print(result.document.invoice_number)
print(result.meta.warnings)

# Persist the JSON
for path in pipeline.process_and_save_all("scan.png"):
    print("written:", path)
```

---

## Supported documents

| Type | Schema highlights |
| --- | --- |
| `invoice` | number, dates, seller/buyer, line items, subtotal, tax, total, currency |
| `passport` | name, nationality, dates, passport number, issuing country |
| `id_card` | name, birth date/place, document number, expiry, authority |
| `prescription` | patient, prescriber, drug list with dosage/frequency/duration |
| `certificate` | title, person, issue date, authority, details |
| `generic_form` | free-form `fields` dictionary for anything else |

Adding a type is one class in `src/idp/schemas.py` plus one entry in
`SCHEMA_REGISTRY` -- the prompt, the validation and the routing pick it up
automatically.

---

## Output format

Each processed file produces one JSON document in `data/processed/`:

```json
{
  "document_type": "invoice",
  "invoice_number": "INV-2024-001",
  "date": "2024-03-12",
  "seller_name": "ACME SARL",
  "items": [
    { "description": "Widget", "quantity": 2.0, "unit_price": 50.0, "total_price": 100.0 }
  ],
  "subtotal": 100.0,
  "tax_amount": 20.0,
  "total_amount": 120.0,
  "currency": "EUR",
  "_meta": {
    "provider": "ollama",
    "ocr_engine": "ollama-vision:llama3.2-vision",
    "extraction_model": "llama3.2",
    "source_file": "invoice_2024.png",
    "document_type": "invoice",
    "processed_at": "2024-03-12T09:14:22.481+00:00",
    "duration_ms": 18422,
    "from_cache": false,
    "page": null,
    "warnings": []
  }
}
```

The `_meta.warnings` list is the human-in-the-loop hook: surface it in your own
review UI to decide which documents need a second look.

---

## Quality: tests, lint, pre-commit

```bash
pytest -q                     # 60+ tests, no network required
ruff check .                  # style and likely-bug checks
pytest --cov=idp              # coverage report
pre-commit install            # optional git hooks
```

Tests use fake OCR and fake LLM clients, so the whole suite runs offline in a
few seconds -- that is also why it can run in CI on every pull request.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Ollama est injoignable` | Start it with `ollama serve`, check `OLLAMA_HOST` |
| `model requires more system memory` | Use a smaller vision model, or lower `OLLAMA_MAX_IMAGE_SIDE` |
| `VERTEX_PROJECT_ID n'est pas renseigne` | Set it in `.env` (not in the source code) |
| `google.auth.exceptions.DefaultCredentialsError` | Run `gcloud auth application-default login` |
| PDF ignored | Install the extra: `pip install -e ".[pdf]"` |
| Result looks stale | The cache is content-addressed: disable it with `IDP_USE_CACHE=false` |
| Slow local OCR | Normal on CPU. `OLLAMA_MAX_IMAGE_SIDE=768` speeds it up further |

---

## Roadmap

- [ ] Multi-page PDF merge into a single document
- [ ] Confidence score per field (log-probabilities / self-consistency)
- [ ] Batch CLI with a manifest and retry queue
- [ ] Export to CSV / Excel in addition to JSON
- [ ] Docker image published to GHCR
- [ ] Optional human-in-the-loop review screen

Contributions on any of these are welcome -- see
[CONTRIBUTING.md](CONTRIBUTING.md).

---

## Contributing

Issues and pull requests are welcome. Please read
[CONTRIBUTING.md](CONTRIBUTING.md) first, and note that the project follows the
[Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).

For a security issue, please follow [SECURITY.md](SECURITY.md) instead of
opening a public issue.
