# LearnX Research Website

HTML and CSS publication for SLIIT research project R26-SE-041. The visual design follows the warm ivory, bold typography and editorial layout of the supplied Anthropic reference, with LearnX branding.

## Local preview

Run `node tools/preview.mjs` from this folder, then open http://127.0.0.1:4173.

## GitHub and Vercel

Repository: https://github.com/R26-SE-041/R26-SE-041

Live website: https://learnx-research.vercel.app

Vercel project: https://vercel.com/kojithan-ys-projects/learnx-research

The GitHub repository is connected to Vercel with:

- Project name: learnx-research
- Root Directory: learnx-project-website
- Framework Preset: Other
- Build Command: leave empty
- Output Directory: public
- Production Branch: main

Commit and push website changes to main to trigger a production deployment. Changes on other branches produce preview deployments. Only publish the files under this website folder; original PowerPoints in source/presentations are excluded.

## Editing

- public/index.html: all seven required sections and document links
- public/styles.css: shared responsive theme
- public/assets/documents: nine original PDFs with consistent filenames
- public/assets/images: restored team portraits, updated co-supervisor portrait and favicon
- public/view: legacy reader pages retained for existing bookmarks
- vercel.json: static hosting configuration

## Course submission

Upload the public directory contents or the standalone ZIP, with index.html at the upload root. Vercel publishing does not submit files to the course web. The full public website is below 20 MB.

## Source content

Research content comes from the supplied research paper and Topic Assessment Form. The visual component section also describes the current repository implementation: sketch-agent/README.md and shared/sketch.py (SDXL/Scribble), orchestrator/graph.py (harness), studio/pipeline.py (sketch labeling/history), prompt-agent/modal_app.py (system prompts) and shared/image_policies.py (executable generation policies). Team names and original member portraits come from PP2 page 2; the co-supervisor portrait uses the replacement photograph supplied by the user. Member portraits were restored with the built-in image editing tool, with originals retained locally in source/portraits; team contact details and responsibilities come from existing project documentation. Four individual component reports are supplied separately and retained unchanged. The library contains all nine PDFs supplied for the website.

Milestone dates now follow the RP Team 2026 Regular Batch timeline screenshot supplied by the user. The assessment cards show their scheduled dates and an expandable full timeline lists all 13 deadlines. Allocated marks remain omitted by user instruction. The project repository is linked from the home section and footer. Final presentation and final/viva assessment materials have not been supplied; future entries remain available. Individual reports are not relabeled as final reports. No additional files have been requested.

Each document and presentation offers a direct PDF link that opens in a new browser tab and a separate Download link. Browser PDF settings control inline viewing. Legacy reader pages remain available for existing bookmarks. The site has no frontend JavaScript or package dependencies.

Models by research component: the Technologies section maps configured frontends, Python backends, databases and GPU serving from this repository. Published base-model/checkpoint parameter sizes link to source model cards; rounded figures and unavailable custom counts are labeled. LoRA trainable counts are separate. The static website hosting is described separately from the research application stack.
