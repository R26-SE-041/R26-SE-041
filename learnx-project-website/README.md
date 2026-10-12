# LearnX Research Website

Research website for SLIIT project R26-SE-041, presenting the project overview, research components, technologies, milestones, team, and document library.

**Live website:** https://learnx-research.vercel.app

## Local preview

From this directory:

```bash
node tools/preview.mjs
```

Open http://127.0.0.1:4173.

## Files

| Path | Purpose |
| --- | --- |
| `public/index.html` | Website sections and document links |
| `public/styles.css` | Responsive styles |
| `public/assets/documents/` | Research documents, presentations, and component reports |
| `public/assets/images/` | Team portraits and favicon |
| `public/view/` | Document reader pages |
| `project-content.json` | Project, team, and document metadata |
| `vercel.json` | Static hosting configuration |

## Hosting

The `learnx-research` Vercel project is connected to this repository with:

- Root directory: `learnx-project-website`
- Framework preset: Other
- Build command: empty
- Output directory: `public`
- Production branch: `main`

Website changes pushed to `main` trigger production deployment. Other branches provide preview deployments. The site uses HTML and CSS without JavaScript dependencies.

Documents have separate View and Download links. Keep asset filenames and reader URLs stable when updating documents.
