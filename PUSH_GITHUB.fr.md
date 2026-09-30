# Publier la présentation sur GitHub

Ce dossier est une copie complète du dépôt avec la nouvelle présentation dans `presentation/`. Son historique Git et son remote `origin` ont été conservés.

Depuis PowerShell, ouvrir ce dossier, puis :

```powershell
git status
git add presentation .github/workflows/pages.yml README.fr.md PUSH_GITHUB.fr.md
git commit -m "Add interactive IDP presentation"
git push origin main
```

Dans GitHub, aller dans **Settings → Pages → Build and deployment → Source**, puis sélectionner **GitHub Actions**. Après la réussite du workflow **Deploy presentation to GitHub Pages**, le site sera disponible à :

`https://evanguennou29.github.io/intelligent-document-processing-multimodal-genai-main/`

La présentation est indépendante des clés API. L'application Streamlit et le pipeline Python restent dans le même dépôt et conservent leur configuration actuelle.
