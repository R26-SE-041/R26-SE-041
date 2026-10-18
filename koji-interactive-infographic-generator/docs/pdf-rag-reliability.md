# PDF answer reliability

Selected PDFs supply the facts; the image identifies the selected subject. PDF
excerpts are untrusted data and do not override the student's request.

After image identification, PDF answer generation is text-only. It does not
require the PDF to describe the exact generated illustration. The PDF-only prompt
preserves all supplied evidence and excludes unrelated image/persona memory.
PDF mode uses extractive study points, preserving original PDF wording rather
than generating unverified paraphrases. The constrained JSON schema lets the model
select up to eight relevant sentences from the actual supplied excerpts. The app
rejects invented sentences, removes duplicates, locates each sentence's source,
and renders that citation. It creates the bibliography
from the original filename/page metadata. The output budget is 2,048 tokens so
the structured response has room to close; invalid or incomplete JSON is rejected.

The CPU worker also supports older agents during rollout. A draft with missing
or invalid citations receives at most one citation retry with the same evidence
and original question. Valid grouped citations such as `[1, 2]` are accepted only
when every number exists. Transport/service failures are not replayed. If a full
answer cannot be verified, the user receives clearly identified original PDF
passages with page references. An uncited draft never receives invented citations.
No retrieved evidence still produces the existing no-match response.

Interaction metadata records `answerMethod`: `pdf_generated`, `pdf_retry`,
`pdf_passages`, `no_match`, or `image`. Existing failed questions are not rewritten;
ask a new question after rollout.

## Validation

From `backend/`, run `python ../ci/check.py`. Database integration tests require
`STUDIO_TEST_DATABASE_URL`; mock tests do not verify a production database.

To test the candidate model without replacing production endpoints, run:

```powershell
python evaluation/smoke_pdf_grounding.py --pdf "C:/path/Heart_Parts_Text_Only.pdf" --profile ikojikn --concept "Human heart" --report ../../tmp/rag-heart-candidate.json
```

This runs a temporary A100 inference using actual extracted PDF passages and a known
concept. It checks live text generation/citations, not
database retrieval, authentication, or image identification. Inspect the saved
answer for relevance as well as checking the automated citation result.
The default exam-revision smoke test requires at least four distinct points;
use `--min-points 1` when testing a narrow factual question.

Candidate validation on 2026-10-18 used the actual two-page heart study PDF and
"explain this in the exam point of view" on `ikojikn`. The final candidate returned
eight useful original study sentences with verified references to pages 1 and 2.
Local API DNS was temporarily resolved once for that test process; TLS verification
remained enabled. This was candidate inference, not a production release or a
production database retrieval test.

## Production rollout and demo check

Release the tested CPU worker through the existing GitHub Actions production
workflow. Update the interactive agent in all three registered Modal profiles
using `python deploy/modal/deploy_accounts.py --all --services interactive` from
the component root. Keep the same tested source revision across deployments.
Updating only the currently active profile leaves standby profiles outdated.
No database migration or frontend change is required for this fix.

Before the demo, ask a new question with the uploaded PDF selected: "explain this
in the exam point of view". Check that the answer is relevant, its citations open
the correct pages, and the displayed passages support its claims. Also check a
question outside the PDF's scope: it should acknowledge missing evidence rather
than invent an answer. Verify the active account with `switch-modal.ps1 -Action
status`. Campus TLS interception and Modal capacity/credits are separate runtime
dependencies; a passing health check does not exercise GPU inference.
