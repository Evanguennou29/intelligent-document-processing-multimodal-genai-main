# Intelligent Document Processing - Multimodal GenAI

[![CI](https://github.com/Evanguennou29/intelligent-document-processing-multimodal-genai-main/actions/workflows/ci.yml/badge.svg)](https://github.com/Evanguennou29/intelligent-document-processing-multimodal-genai-main/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Transformez des scans, des photos et des PDF en **JSON structure et valide**,
avec un seul pipeline qui tourne soit :

* dans le cloud -- **Google Vertex AI / Gemini Vision** ;
* entierement en local -- **Ollama** avec un modele de vision.

Le moteur se choisit depuis l'interface, la ligne de commande, ou une simple
variable d'environnement.

> [English version](README.md)

---

## Ce qui change en v2.0

| Domaine | Avant | Maintenant |
| --- | --- | --- |
| Configuration | `PROJECT_ID` code en dur | tout dans `.env` (voir `.env.example`) |
| Code duplique | 3 paires de fichiers quasi identiques | une seule implementation par responsabilite |
| Validation | fonction qui ne validait rien | dates normalisees, arithmetique des factures, documents expires |
| Parsing JSON | split naif sur les balises de code | extraction robuste + une tentative de reparation |
| PDF | `pymupdf` declare mais inutilise | PDF scannes rasterises et traites |
| Cache | aucun | cache par empreinte du fichier, desactivable |
| Routage | `if "id" in filename` matchait `video.mp4` | detection par mots entiers + repli sur le texte OCR |
| Tests / CI | aucun | 60+ tests pytest hors ligne + GitHub Actions |
| Docker | aucun | `Dockerfile` + `docker-compose.yml` (app + Ollama) |

---

## Installation rapide

```bash
git clone https://github.com/Evanguennou29/intelligent-document-processing-multimodal-genai-main.git
cd intelligent-document-processing-multimodal-genai-main

python -m venv .venv
# Windows : .\.venv\Scripts\Activate.ps1
# macOS / Linux : source .venv/bin/activate

pip install -r requirements.txt      # ou requirements_ollama.txt / requirements_vertex.txt
copy .env.example .env               # cp sous macOS / Linux
```

Backend local :

```bash
ollama pull llama3.2-vision
ollama pull llama3.2
ollama serve
```

Backend cloud :

```bash
gcloud auth application-default login
# puis renseignez VERTEX_PROJECT_ID dans .env
```

Lancement de l'interface :

```bash
streamlit run app/streamlit_app.py
```

Puis ouvrez <http://localhost:8501>.

---

## Utilisation

```bash
# Etat de la configuration et des moteurs
python -m idp info

# Traiter un fichier ou un dossier
python -m idp process ./scans -o ./out -p ollama
python -m idp process facture.pdf -t invoice --print
```

En Python :

```python
from idp import Pipeline

result = Pipeline(provider="vertex").process("facture.png")
print(result.document.total_amount)
print(result.meta.warnings)
```

---

## Qualite

```bash
pip install -e ".[dev]"
pytest -q
ruff check .
```

---

## Licence

MIT -- voir [LICENSE](LICENSE).

Projet derive du depot pedagogique
[`lucieadc/intelligent-document-processing-multimodal-genai`](https://github.com/lucieadc/intelligent-document-processing-multimodal-genai).
Merci a son autrice pour l'idee d'origine et le notebook d'evaluation.
