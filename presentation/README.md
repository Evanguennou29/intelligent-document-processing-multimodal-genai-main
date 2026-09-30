# Présentation web IDP

Présentation statique et interactive du pipeline Intelligent Document Processing. Les quatre documents affichés sont fictifs. Les résultats sont des exemples intégrés au site : cette présentation n'appelle ni Vertex AI ni Ollama et ne traite pas les fichiers du visiteur.

## Voir localement

Ouvrir `index.html` dans un navigateur, ou lancer un serveur HTTP depuis ce dossier :

```powershell
python -m http.server 8080
```

Puis ouvrir `http://localhost:8080`.

## Publication avec GitHub Pages

Le workflow `.github/workflows/pages.yml` publie ce dossier sur GitHub Pages après un push sur `main`. Dans **Settings → Pages**, choisir **GitHub Actions** comme source. L'URL publique attendue est :

`https://evanguennou29.github.io/intelligent-document-processing-multimodal-genai-main/`

Cette URL ne devient active qu'après activation de Pages et réussite du workflow. Voir `PUSH_GITHUB.fr.md` à la racine pour les commandes Git.
