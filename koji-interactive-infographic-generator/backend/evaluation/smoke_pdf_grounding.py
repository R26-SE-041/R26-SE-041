"""Run candidate PDF answer generation on Modal without replacing live endpoints.

This checks text grounding with a supplied concept, not image identification or
database retrieval. Run from backend/; the named profile must have model weights.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--concept", required=True)
    parser.add_argument("--question", default="explain this in the exam point of view")
    parser.add_argument("--min-points", type=int, default=4,
                        help="Minimum distinct study points; use 1 for a narrow factual question")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if not 1 <= args.min_points <= 8:
        parser.error("--min-points must be between 1 and 8")
    for key in ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "MODAL_OAUTH_CLIENT_ID", "MODAL_OAUTH_CLIENT_SECRET"):
        os.environ.pop(key, None)
    os.environ["MODAL_PROFILE"] = args.profile
    os.environ["MODAL_ENVIRONMENT"] = "main"
    os.chdir(BACKEND)

    from shared.citations import cited_sources
    from studio.documents import extract_chunks, evidence_context, checked_pdf_answer

    chunks, pages, skipped = extract_chunks(args.pdf.read_bytes())
    # Representative evidence only: retrieval quality is tested separately.
    context, sources = evidence_context([
        {**chunk, "document_id":"smoke-test", "filename":args.pdf.name}
        for chunk in chunks[:4]
    ])
    if len(context) > 6500:
        raise ValueError("Evidence exceeds the production PDF context limit")
    path = BACKEND / "agents/interactive-agent/modal_app.py"
    spec = importlib.util.spec_from_file_location("interactive_pdf_candidate", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    with module.app.run():
        result = module.VLMAgentA100().analyze.remote(
            image_bytes=b"", highlighted_image_bytes=b"",
            mode="ask", question=args.question, rag_context=context,
            identified_concept=args.concept, pdf_only=True,
            pdf_sources=[{"number":s["number"],"excerpt":s["excerpt"]} for s in sources],
        )
    answer = result.get("response_text") or ""
    report = {"profile":args.profile, "pdf":args.pdf.name, "pages":pages,
              "skipped_pages":skipped, "question":args.question,
              "raw_answer":answer, "error":result.get("error"),
              "raw_response":result.get("raw_response"),
              "answer":checked_pdf_answer(answer,sources), "sources":sources,
              "scope":"Live candidate text grounding; no database retrieval or image identification"}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    if result.get("error"):
        raise RuntimeError(result["error"])
    if not cited_sources(answer,sources):
        raise RuntimeError("Candidate model answer did not contain valid PDF citations; see report")
    if sum(line.startswith("- [") for line in answer.splitlines()) < args.min_points:
        raise RuntimeError("Candidate model returned too few useful study points; see report")
    print("PASS: candidate model returned valid citations from the actual PDF")
    print("Report:",args.report)


if __name__ == "__main__":
    main()
