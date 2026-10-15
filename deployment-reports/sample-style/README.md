# Sample-style deployment reports

The four content JSON files contain the complete expanded report blocks and component metadata used for the final PDFs. They are generated from the original concise Markdown reports plus component-specific academic sections in `tools/build_sample_style_deployment_reports.py`.

The supplied senior PDF was used as a formatting and structural reference, including the existing SLIIT logo. Its Kubernetes-specific environment, incidents, results and user feedback were not adopted as BioLearnX facts. All four reports retain the evidence limits of the current repository.

The final reports contain deployment overview, deployment process, issues/resolution/monitoring, and post-deployment validation/documentation/lessons. Automatic contents page numbers and PDF bookmarks refer to the numbered body pages. Rendered page previews and validation metadata are kept under `tmp/pdfs/deployment-reports-sample-style`.
