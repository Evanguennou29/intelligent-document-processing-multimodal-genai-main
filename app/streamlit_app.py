"""Streamlit front-end for the Intelligent Document Processing pipeline.

Run it with::

    streamlit run app/streamlit_app.py

The ``src`` folder is added to ``sys.path`` so the app also works from a
fresh clone without installing the package first.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from idp.config import PROVIDERS, get_settings  # noqa: E402
from idp.errors import IdpError  # noqa: E402
from idp.pipeline import Pipeline  # noqa: E402
from idp.schemas import DocumentType  # noqa: E402

ACCEPTED_TYPES = ["png", "jpg", "jpeg", "webp", "tif", "tiff", "pdf"]
PROVIDER_LABELS = {
    "vertex": "Google Vertex AI (cloud)",
    "ollama": "Ollama (local, prive)",
}
DOC_TYPE_CHOICES = {"Detection automatique": None}
DOC_TYPE_CHOICES.update({name.value.replace("_", " ").title(): name.value for name in DocumentType})

st.set_page_config(
    page_title="Intelligent Document Processing",
    page_icon="\U0001F4C4",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .stApp {
            background-color: #F3F4F6;
            background-image: radial-gradient(#E5E7EB 1px, transparent 1px);
            background-size: 20px 20px;
        }
        section[data-testid="stSidebar"] {
            background-color: #FFFFFF;
            border-right: 1px solid #E5E7EB;
        }
        section[data-testid="stSidebar"] * { color: #111827 !important; }
        .css-card {
            background: #FFFFFF;
            border-radius: 16px;
            padding: 28px;
            border: 1px solid #EEF0F3;
            box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
            margin-bottom: 20px;
        }
        .card-header { font-size: 1.2rem; font-weight: 700; color: #1F2937; margin-bottom: 4px; }
        .card-sub { color: #6B7280; font-size: 0.9rem; }
        div.stButton > button {
            background: linear-gradient(135deg, #4F46E5 0%, #3730A3 100%);
            color: #FFFFFF;
            font-weight: 600;
            padding: 14px 22px;
            border-radius: 12px;
            border: none;
            width: 100%;
        }
        div.stButton > button:hover { background: linear-gradient(135deg, #4338CA 0%, #312E81 100%); }
        pre { background-color: #0F172A !important; border-radius: 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- #
# Cached helpers
# --------------------------------------------------------------------------- #
@st.cache_resource(show_spinner=False)
def get_pipeline(provider: str, use_cache: bool) -> Pipeline:
    return Pipeline(provider=provider, use_cache=use_cache)


@st.cache_data(ttl=20, show_spinner=False)
def engine_health(provider: str) -> dict:
    """Probe a provider without blowing up the UI when it is unreachable."""
    try:
        return Pipeline(provider=provider).health()
    except Exception as exc:  # noqa: BLE001 - diagnostic only
        return {
            "ocr": {"ok": False, "detail": str(exc), "engine": "?"},
            "extractor": {"ok": False, "detail": str(exc), "model": "?"},
        }


def load_settings():
    get_settings.cache_clear()
    return get_settings()


def save_upload(uploaded_file, doc_type: str | None) -> Path:
    settings = load_settings()
    folder = settings.data_raw_dir / (doc_type or "auto")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / Path(uploaded_file.name).name
    target.write_bytes(uploaded_file.getbuffer())
    return target


def invoice_rows(payload: dict) -> list[dict]:
    return [
        {
            "description": item.get("description", ""),
            "quantity": item.get("quantity"),
            "unit_price": item.get("unit_price"),
            "total_price": item.get("total_price"),
        }
        for item in payload.get("items", [])
        if isinstance(item, dict)
    ]


# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
st.markdown(
    """
    <div style="text-align:center; margin-bottom:24px;">
        <h1 style="color:#111827; font-size:2.6rem; font-weight:800; letter-spacing:-1px; margin-bottom:4px;">
            Intelligent Document Processing
        </h1>
        <p style="color:#6B7280; font-size:1.1rem; margin:0;">
            Orchestration hybride :
            <span style="color:#4F46E5; font-weight:600;">Google Vertex AI</span> ou
            <span style="color:#EA580C; font-weight:600;">Ollama local</span>
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

settings = load_settings()

# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown("### Configuration")

    provider = st.radio(
        "Moteur d'IA",
        PROVIDERS,
        index=PROVIDERS.index(settings.provider) if settings.provider in PROVIDERS else 0,
        format_func=lambda value: PROVIDER_LABELS.get(value, value),
    )

    st.divider()

    selected_label = st.selectbox("Type de document", list(DOC_TYPE_CHOICES.keys()))
    doc_type = DOC_TYPE_CHOICES[selected_label]

    use_cache = st.toggle("Utiliser le cache", value=settings.use_cache)

    st.divider()
    health = engine_health(provider)
    ocr_health = health.get("ocr", {})
    extractor_health = health.get("extractor", {})

    if ocr_health.get("ok"):
        st.success(f"OCR pret : {ocr_health.get('engine')}")
    else:
        st.error(f"OCR indisponible\n\n{ocr_health.get('detail')}")

    if extractor_health.get("ok"):
        st.success(f"Extraction prete : {extractor_health.get('model')}")
    else:
        st.error(f"Extraction indisponible\n\n{extractor_health.get('detail')}")

    if provider == "vertex" and not settings.vertex_configured():
        st.warning("Renseignez VERTEX_PROJECT_ID dans votre fichier .env.")

    st.divider()
    with st.expander("Configuration effective"):
        st.json(settings.describe())

# --------------------------------------------------------------------------- #
# Upload / run
# --------------------------------------------------------------------------- #
left, right = st.columns([1, 1], gap="large")

with left:
    st.markdown(
        """
        <div class="css-card">
            <div class="card-header">1. Importation</div>
            <div class="card-sub">Deposez une ou plusieurs images, ou un PDF scanne.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    uploaded_files = st.file_uploader(
        "Fichiers",
        type=ACCEPTED_TYPES,
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if uploaded_files:
        for uploaded in uploaded_files:
            st.caption(f"\u2705 {uploaded.name} ({uploaded.size / 1024:.0f} Ko)")

with right:
    st.markdown(
        f"""
        <div class="css-card">
            <div class="card-header">2. Extraction ({provider.upper()})</div>
            <div class="card-sub">L'IA lit le document, structure les donnees et valide le JSON.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    run = st.button(
        f"LANCER L'ANALYSE ({provider.upper()})",
        disabled=not uploaded_files,
    )

    if not uploaded_files:
        st.info("En attente d'un document...")

if run and uploaded_files:
    pipeline = get_pipeline(provider, use_cache)
    health = pipeline.health()
    if not health["ocr"]["ok"]:
        st.error(f"OCR indisponible : {health['ocr']['detail']}")
        st.stop()
    if not health["extractor"]["ok"]:
        st.error(f"Extraction indisponible : {health['extractor']['detail']}")
        st.stop()

    progress = st.progress(0.0, text="Preparation...")
    results: list[tuple[str, dict]] = []
    errors: list[tuple[str, str]] = []

    for index, uploaded in enumerate(uploaded_files):
        progress.progress(index / len(uploaded_files), text=f"Traitement de {uploaded.name}...")
        try:
            path = save_upload(uploaded, doc_type)
            outputs = pipeline.process_and_save_all(path, out_dir=settings.data_processed_dir)
            for output in outputs:
                payload = json.loads(Path(output).read_text(encoding="utf-8"))
                page = payload.get("_meta", {}).get("page")
                label = f"{uploaded.name} (page {page})" if page else uploaded.name
                results.append((label, payload))
        except IdpError as exc:
            errors.append((uploaded.name, str(exc)))
        except Exception as exc:  # noqa: BLE001 - surface the message to the user
            errors.append((uploaded.name, f"Erreur inattendue : {exc}"))

    progress.progress(1.0, text="Termine")

    for name, message in errors:
        st.error(f"{name} : {message}")

    if results:
        st.success(f"{len(results)} document(s) traite(s) avec succes.")
        tabs = st.tabs([label for label, _ in results])
        for tab, (label, payload) in zip(tabs, results):
            with tab:
                meta = payload.get("_meta", {})
                warnings = meta.get("warnings") or []
                for warning in warnings:
                    st.warning(warning)

                st.json(payload)

                columns = st.columns(2)
                with columns[0]:
                    st.download_button(
                        "Telecharger le JSON",
                        data=json.dumps(payload, indent=2, ensure_ascii=False),
                        file_name=f"{Path(label).stem}.json",
                        mime="application/json",
                        use_container_width=True,
                    )
                with columns[1]:
                    rows = invoice_rows(payload)
                    if rows:
                        buffer = io.StringIO()
                        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
                        writer.writeheader()
                        writer.writerows(rows)
                        st.download_button(
                            "Telecharger les lignes (CSV)",
                            data=buffer.getvalue().encode("utf-8"),
                            file_name=f"{Path(label).stem}-items.csv",
                            mime="text/csv",
                            use_container_width=True,
                        )