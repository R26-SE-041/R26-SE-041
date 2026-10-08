# Contributing to BioLearnX

Read the [repository README](README.md) and the README for the component you want to change.
BioLearnX contains separate components with different setup and test requirements.

## Before making a change

For a substantial feature or a change spanning components, open an issue describing
the problem, proposed behavior and affected folders. Coordinate with the relevant
component maintainers. Report security vulnerabilities privately instead of opening
a public issue; see [the security policy](SECURITY.md).

## Development

1. Create a branch for one focused change.
2. Follow the affected component's setup instructions and existing conventions.
3. Keep credentials in local environment files or hosted secret stores. Commit
   examples with placeholders only.
4. Add meaningful tests for changed behavior and run the relevant existing checks.
5. Update documentation when setup, configuration or user behavior changes.

## Component instructions

Use the setup and validation instructions for each affected component:

| Component | Instructions |
| --- | --- |
| Koji interactive visualization | [Contribution guide](koji-interactive-infographic-generator/CONTRIBUTING.md) and [README](koji-interactive-infographic-generator/README.md) |
| Adaptive quizzes and recommendations | [README](nishy-adaptive-quiz-recommender/README.md) |
| Image-to-notes pipeline | [Repository overview](README.md#intelligent-image-to-notes-workflow) and [component folder](sarmitha-image-text-extractor-study-gen/) |
| Interactive audio communication | [README](baskaran-interactive-audio-communication/README.md) |

Use isolated test data and disposable databases for integration tests. Coordinate
tests that call paid model services with the component maintainer.

## Pull requests

Describe the problem and resulting behavior, name the affected components and
include validation results. Disclose skipped checks and required migrations or
environment changes. Include screenshots for visible UI changes when useful.

Keep unrelated edits out of the pull request. Model outputs used in examples
should exclude personal data. Do not upload restricted datasets or model weights.
Respect the [code of conduct](CODE_OF_CONDUCT.md) and allow maintainers to review before merging.
