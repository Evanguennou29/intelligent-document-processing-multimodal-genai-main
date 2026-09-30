# Contributing

Thanks for taking the time to improve this project.

## Getting started

```bash
git clone https://github.com/Evanguennou29/intelligent-document-processing-multimodal-genai-main.git
cd intelligent-document-processing-multimodal-genai-main
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1   |   macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The test suite never touches the network: OCR and LLM clients are replaced by
fakes, so you can iterate quickly without spending API credits.

## Before opening a pull request

1. `pytest -q` passes.
2. `ruff check .` is clean (`ruff check . --fix` handles most issues).
3. New behaviour is covered by a test.
4. User-facing text stays in ASCII where possible, and documentation is updated.

## Commit messages

Short imperative subject, then a blank line and a body explaining *why*:

```
Add confidence warnings for low-quality OCR

The invoice total was silently wrong when two digits were unreadable.
The extractor now flags any field that could not be read confidently.
```

## Adding a new document type

1. Add the model to `src/idp/schemas.py` and register it in `SCHEMA_REGISTRY`.
2. Add routing keywords in `src/idp/routing.py` (filename and/or text rules).
3. Add business rules in `src/idp/validation.py` if needed.
4. Add tests in `tests/`.

The prompt, the CLI and the web UI pick the new type up automatically.

## Reporting bugs

Please include the backend used, the model names, the document type, the
`_meta` block of the result (it contains no personal data beyond the file name)
and what you expected instead.

**Never paste a real identity document, a real invoice or an API key in an
issue.**