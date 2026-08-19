"""Compare vector, full-text, and hybrid retrieval using annotated queries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from shared.db import full_text_retrieve, hybrid_retrieve, vector_retrieve
from shared.rag import embed


def _precision(results: list[dict[str, Any]], relevant_sources: set[str], k: int) -> float:
    retrieved = [str(item.get("source") or "") for item in results[:k]]
    return sum(source in relevant_sources for source in retrieved) / k


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queries", type=Path, help="JSON array with query and relevant_sources fields")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--k", type=int, default=3)
    args = parser.parse_args()
    queries = json.loads(args.queries.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for item in queries:
        query = str(item["query"])
        relevant = set(map(str, item["relevant_sources"]))
        vector = embed(query)
        modes = {
            "vector": vector_retrieve(vector, n=args.k),
            "full_text": full_text_retrieve(query, n=args.k),
            "hybrid": hybrid_retrieve(query, vector, "knowledge_chunks", n=args.k),
        }
        for mode, results in modes.items():
            rows.append({
                "query": query,
                "mode": mode,
                "precision_at_k": _precision(results, relevant, args.k),
                "sources": [result.get("source") for result in results],
            })
    summary = {
        mode: mean(row["precision_at_k"] for row in rows if row["mode"] == mode)
        for mode in ("vector", "full_text", "hybrid")
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"k": args.k, "summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

