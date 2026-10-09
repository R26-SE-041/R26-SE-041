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
- public/assets/images: portraits extracted from PP2 page 2 and favicon
- public/view: browser PDF readers
- vercel.json: static hosting configuration

## Course submission

Upload the public directory contents or the standalone ZIP, with index.html at the upload root. Vercel publishing does not submit files to the course web. The full public website is below 20 MB.

## Source content

Research content comes from the supplied research paper and Topic Assessment Form. Team names/photos come from PP2 page 2; team contact details and responsibilities come from existing project documentation. Four individual component reports are supplied separately and retained unchanged. The library contains all nine PDFs supplied for the website.

Milestone dates and allocated marks are omitted by explicit user instruction. Final presentation and final/viva assessment materials have not been supplied; future entries remain available. Individual reports are not relabeled as final reports. No additional files have been requested.

PDF readers use native browser rendering, with a direct Open PDF fallback and optional download. The site has no frontend JavaScript or package dependencies.
