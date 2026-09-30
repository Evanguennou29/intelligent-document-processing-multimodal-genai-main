# Security policy

## Reporting a vulnerability

Please do not open a public issue for a security problem. Use GitHub's private
vulnerability reporting ("Security" tab -> "Report a vulnerability") or contact
the maintainer directly.

We aim to acknowledge a report within 72 hours and to publish a fix as soon as
a patched version is available.

## How this project handles sensitive data

Document processing often means identity papers, invoices or medical
prescriptions. A few rules are built into the code:

* **No secret is hard-coded.** Every credential comes from the environment;
  `.env` is git-ignored and `.env.example` only contains empty placeholders.
* **Nothing is transmitted without your decision.** The `ollama` backend is
  100% offline; the `vertex` backend sends the document to Google Cloud, and
  that choice is always explicit in the UI, the CLI or `IDP_PROVIDER`.
* **Local data stays local.** Documents live in `data/raw/`, results in
  `data/processed/`, and both are git-ignored.
* **The cache is local only.** It stores extracted JSON under `.cache/idp/`,
  also git-ignored. Disable it with `IDP_USE_CACHE=false` if your threat model
  forbids plaintext copies of extracted data on disk.

## Supported versions

| Version | Supported |
| --- | --- |
| 2.x | Yes |
| 1.x (original layout) | No |

## Operator checklist

Before exposing this application to other users:

- [ ] Never commit `.env`, a service-account JSON or a `.pem` key.
- [ ] Restrict the Vertex AI service account to the minimum required roles.
- [ ] Put authentication in front of the Streamlit app (it has none by design).
- [ ] Review the retention policy of `data/raw`, `data/processed` and `.cache`.
- [ ] Prefer the `ollama` backend for documents you are not allowed to upload.