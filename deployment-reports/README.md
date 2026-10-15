# BioLearnX — Component Deployment Reports

The current deliverable is the consolidated [BioLearnX group deployment report](../output/pdf/R26-SE-041_BioLearnX_Deployment_Report.pdf), covering all four members and components in one academic report. Its editable source is [BioLearnX_Group_Deployment_Report.md](BioLearnX_Group_Deployment_Report.md), rendered by [the group report builder](../tools/build_group_deployment_report.py). Earlier individual reports below are retained as previous versions.

**Project:** R26-SE-041 | **Institution:** SLIIT | **Prepared:** 14 October 2026

Four independent reports describe the deployment architecture, configuration, release procedure, verification, maintenance, and rollback for each research component.

English PDF editions are available in [output/pdf](../output/pdf/): [Koji](../output/pdf/01-koji-deployment-report.pdf), [Baskaran](../output/pdf/02-baskaran-deployment-report.pdf), [Nishy](../output/pdf/03-nishy-deployment-report.pdf), and [Sarmitha](../output/pdf/04-sarmitha-deployment-report.pdf). These expanded PDFs follow the supplied senior sample's academic structure: cover, SLIIT logo, contents, four numbered chapters, Times New Roman text, page borders and separate body pagination. Koji and Nishy contain 16 pages each; Baskaran and Sarmitha contain 17 pages each.

The original concise Markdown reports below remain as source material. Expanded report content is stored in [sample-style](sample-style/); [the sample-style builder](../tools/build_sample_style_deployment_reports.py) reproduces the final PDF editions. The earlier concise PDF builder does not reproduce these expanded editions.

| Component | Member | Report |
| --- | --- | --- |
| Interactive infographic generation | Kojithan P. Y — IT22264220 | [Koji deployment report](01-koji-deployment-report.md) |
| Multilingual audio communication | Baskaran V — IT22172600 | [Baskaran deployment report](02-baskaran-deployment-report.md) |
| Adaptive quiz and recommendation | Nishara T — IT22223876 | [Nishy deployment report](03-nishy-deployment-report.md) |
| Image enhancement, OCR, and translation | Sarmitha S — IT22637482 | [Sarmitha deployment report](04-sarmitha-deployment-report.md) |

These reports are based on the current repository, not a live infrastructure audit. Documented hosting, source configuration, and proposed deployment steps are distinguished within each report. No cloud deployment, paid inference, database migration, or runtime test was performed while preparing them. Verification commands and acceptance checks are procedures to execute before signing off a release; they are not recorded pass results.

Commands use a Linux deployment shell unless stated otherwise. Replace deployment-specific values through private environment configuration. Existing component reports and research website files remain separate from these deployment documents.
