"""Retrieval ablation: BM25 → dense → hybrid+RRF → hybrid+RRF+reranker.

This is the cheapest strong table in the paper. Three of the four arms cost
nothing at all (BM25 is pure CPU; the dense and RRF arms reuse one embedding
call per query), and only the reranker arm adds GPU work — on a T4, the least
expensive accelerator in the fleet.

The four arms are built from the *same* retrieval code the product runs, so the
ablation measures the deployed system rather than a reimplementation:

  bm25      `_BM25Store.search`                       — sparse only
  dense     `query_chunks`                            — BGE-M3 vectors, Chroma
  hybrid    `_reciprocal_rank_fusion(dense, sparse)`  — RRF, no reranking
  reranked  `hybrid_query_chunks`                     — the full deployed path

Because `recall@k` is order-blind and the reranker only reorders, the
hybrid → reranked delta shows up in nDCG and MRR but barely in recall. Report
all three or the reranker will look useless.

Gold set format — `data/retrieval_gold.json`:

    {"queries": [
      {"id": "q01",
       "query": "What is the origin of the pectoralis major?",
       "relevant_chunk_ids": ["doc1::chunk_14", "doc1::chunk_15"],
       "language": "english"}
    ]}

Chunk ids must match the ids your ingestion pipeline stores in Chroma metadata.
`--dump-chunks` prints what the retriever returns for one query so the ids can
be read off directly while annotating.

Usage:
    python -m benchmarks.eval_retrieval --user-id <uid> --dump-chunks "your query"
    python -m benchmarks.eval_retrieval --user-id <uid> --arms bm25,dense
    python -m benchmarks.eval_retrieval --user-id <uid> --arms all
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BENCH_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from benchmarks.metrics import bootstrap_ci, retrieval_report  # noqa: E402

GOLD = BENCH_DIR / "data" / "retrieval_gold.json"
RESULTS_DIR = BENCH_DIR / "results"
ARMS = ["bm25", "dense", "hybrid", "reranked"]
TOP_K = 10


def chunk_id(chunk: dict) -> str:
    """Content-addressed identifier for a retrieved chunk.

    Deliberately keyed on the text alone, not on document_id. The live Chroma
    store holds 298 embeddings covering only 18 distinct passages: the same two
    PDFs were re-ingested about seventeen times, each pass minting a fresh
    document_id for identical text. Keying on document_id would give those
    copies seventeen different ids, so a retriever returning ten copies of
    exactly the right passage would score recall ≈ 0.06 against a gold set that
    named one of them. Identical text is identical evidence; it gets one id.

    `hashlib`, never the builtin `hash()`: Python randomises string hashing per
    process, so builtin-hash ids would differ between the `--dump-chunks` run
    used to annotate the gold set and the evaluation run that reads it, and
    every query would score zero for reasons invisible in the output.

    Hashing the first 200 whitespace-normalised characters keeps the id stable
    when a re-ingest changes only spacing or page-break artefacts, which would
    otherwise silently invalidate an annotated set.
    """
    meta = chunk.get("metadata") or {}
    explicit = next(
        (meta[k] for k in ("chunk_id", "id", "chunk_index") if meta.get(k) is not None),
        None,
    )
    if explicit is not None:
        return f"{meta.get('document_id', 'doc')}::{explicit}"

    text = " ".join((chunk.get("text") or "").split())[:200]
    return "sha:" + hashlib.md5(text.encode("utf-8")).hexdigest()[:16]


def corpus_stats(chroma_path: Path | None = None) -> dict:
    """Report what is actually indexed, straight from Chroma's SQLite store.

    Run this before trusting any retrieval number. Two corpus properties
    invalidate a retrieval table outright, and neither is visible from the
    metrics themselves:

      * **Duplication.** Re-ingesting a document mints new ids for identical
        text. A corpus that is 94% duplicates has far less evidence in it than
        the embedding count suggests, and top-k fills with copies.
      * **Domain.** Retrieval scores describe the indexed corpus, not the one a
        paper claims to serve. A table built on whatever happens to be in the
        dev database is not a result about lecture material.
    """
    path = chroma_path or (BACKEND_DIR / "chroma_data" / "chroma.sqlite3")
    if not path.exists():
        return {"error": f"no Chroma store at {path}"}

    con = sqlite3.connect(str(path))
    query = """
        SELECT em.id,
               MAX(CASE WHEN em.key='chroma:document' THEN em.string_value END) AS doc,
               MAX(CASE WHEN em.key='filename'        THEN em.string_value END) AS fn,
               MAX(CASE WHEN em.key='document_id'     THEN em.string_value END) AS did
        FROM embedding_metadata em GROUP BY em.id
    """
    rows = [r for r in con.execute(query) if r[1]]
    con.close()

    by_text: dict[str, int] = {}
    by_file: dict[str, int] = {}
    documents: set[str] = set()
    for _rid, doc, filename, document_id in rows:
        key = " ".join(doc.split())[:200]
        by_text[key] = by_text.get(key, 0) + 1
        by_file[filename or "?"] = by_file.get(filename or "?", 0) + 1
        if document_id:
            documents.add(document_id)

    distinct = len(by_text)
    return {
        "embeddings": len(rows),
        "distinct_passages": distinct,
        "duplication_factor": round(len(rows) / distinct, 1) if distinct else 0,
        "distinct_document_ids": len(documents),
        "files": by_file,
        "most_duplicated": sorted(by_text.values(), reverse=True)[:5],
    }


async def run_arm(arm: str, query: str, user_id: str, k: int) -> tuple[list[str], float]:
    """Execute one retrieval arm; return (ranked chunk ids, elapsed seconds)."""
    from app.services import ingestion

    started = time.perf_counter()

    if arm == "bm25":
        await ingestion._ensure_bm25_loaded(user_id)
        chunks = ingestion._bm25_store.search(user_id, query, top_k=k)

    elif arm == "dense":
        chunks = await ingestion.query_chunks(query, user_id, n_results=k)

    elif arm == "hybrid":
        # RRF over the same two candidate lists the full pipeline fuses, but
        # stopping before the cross-encoder — this is the arm that isolates the
        # reranker's contribution.
        await ingestion._ensure_bm25_loaded(user_id)
        dense = await ingestion.query_chunks(query, user_id, n_results=k)
        sparse = ingestion._bm25_store.search(user_id, query, top_k=k)
        chunks = ingestion._reciprocal_rank_fusion(dense, sparse)[:k]

    elif arm == "reranked":
        chunks = await ingestion.hybrid_query_chunks(query, user_id, n_results=k)

    else:
        raise ValueError(f"unknown arm: {arm}")

    return [chunk_id(c) for c in chunks], time.perf_counter() - started


async def dump_chunks(query: str, user_id: str) -> None:
    """Print the retriever's output for one query, to annotate a gold set."""
    ids, elapsed = await run_arm("reranked", query, user_id, TOP_K)
    from app.services import ingestion

    chunks = await ingestion.hybrid_query_chunks(query, user_id, n_results=TOP_K)
    print(f"\nquery: {query}   ({elapsed:.2f}s)\n")
    for rank, (cid, chunk) in enumerate(zip(ids, chunks), start=1):
        text = (chunk.get("text") or "").replace("\n", " ")[:150]
        print(f"{rank:2d}. {cid}")
        print(f"    score={chunk.get('score', 0):.4f}  {text}…\n")


async def main_async(args) -> int:
    if args.corpus_stats:
        stats = corpus_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        factor = stats.get("duplication_factor", 1)
        if factor and factor > 1.5:
            print(
                f"\nWARNING: every passage is stored ~{factor}x. Top-k fills with "
                f"copies of the same text, and any recall@k computed over "
                f"document-scoped ids is wrong by roughly that factor. chunk_id() "
                f"is content-addressed to compensate, but the real fix is to clear "
                f"and re-ingest the corpus once."
            )
        return 0

    if args.dump_chunks:
        await dump_chunks(args.dump_chunks, args.user_id)
        return 0

    if not GOLD.exists():
        print(f"No gold set at {GOLD}.\n"
              f"Build one with --dump-chunks, then annotate relevant_chunk_ids. "
              f"80-120 queries is enough for stable nDCG@10.")
        return 1

    payload = json.loads(GOLD.read_text(encoding="utf-8"))
    queries = payload["queries"]
    arms = ARMS if args.arms == "all" else [a.strip() for a in args.arms.split(",")]

    results: dict[str, dict] = {}
    failed_arms: dict[str, str] = {}
    for arm in arms:
        print(f"\n── arm: {arm}")
        runs, latencies, per_query = [], [], []
        first_error = None
        for case in queries:
            gold_ids = set(case["relevant_chunk_ids"])
            try:
                ranked, elapsed = await run_arm(arm, case["query"], args.user_id, TOP_K)
            except Exception as exc:
                if first_error is None:
                    first_error = f"{type(exc).__name__}: {exc}"
                    print(f"   [{case['id']}] FAILED {first_error}")
                else:
                    print(f"   [{case['id']}] FAILED {type(exc).__name__}")
                continue
            runs.append((ranked, gold_ids))
            latencies.append(elapsed * 1000)
            per_query.append({
                "id": case["id"],
                "query": case["query"],
                "language": case.get("language", "english"),
                "gold": sorted(gold_ids),
                "ranked": ranked,
                "latency_ms": round(elapsed * 1000, 1),
            })
            print(f"   [{case['id']}] {elapsed * 1000:7.1f} ms  "
                  f"{len(set(ranked[:5]) & gold_ids)}/{len(gold_ids)} gold in top-5")

        # An arm where every query raised has no metrics — it has an error.
        # Scoring the empty run list would emit a full row of 0.000, which reads
        # exactly like a real measurement of a retriever that finds nothing.
        # Refuse to produce that number; report the cause instead.
        if not runs:
            failed_arms[arm] = first_error or "every query failed"
            print(f"   → arm '{arm}' produced no results: {failed_arms[arm]}")
            continue

        report = retrieval_report(runs)
        # Per-query recall@5 drives the CI: it is the quantity a reader will
        # compare across arms, so it is the one that needs an interval.
        from benchmarks.metrics import recall_at_k
        recalls = [recall_at_k(r, g, 5) for r, g in runs]
        report["recall@5_ci95"] = bootstrap_ci(recalls)
        report["latency_ms_mean"] = round(sum(latencies) / len(latencies), 1)
        report["queries_scored"] = len(runs)
        report["queries_failed"] = len(queries) - len(runs)
        results[arm] = {"metrics": report, "per_query": per_query}

        if report["queries_failed"]:
            print(f"   ! {report['queries_failed']} of {len(queries)} queries failed; "
                  f"metrics cover the remaining {len(runs)}")
        print(f"   → recall@5 {report.get('recall@5', 0):.3f} "
              f"CI{report['recall@5_ci95']}  nDCG@10 {report.get('ndcg@10', 0):.3f}  "
              f"MRR {report.get('mrr', 0):.3f}")

    print(f"\n{'arm':<12}{'R@1':>8}{'R@5':>8}{'R@10':>8}{'nDCG@10':>10}"
          f"{'MRR':>8}{'ms':>9}")
    for arm in arms:
        if arm not in results:
            continue
        m = results[arm]["metrics"]
        print(f"{arm:<12}{m.get('recall@1', 0):>8.3f}{m.get('recall@5', 0):>8.3f}"
              f"{m.get('recall@10', 0):>8.3f}{m.get('ndcg@10', 0):>10.3f}"
              f"{m.get('mrr', 0):>8.3f}{m['latency_ms_mean']:>9.1f}")

    if failed_arms:
        print("\nfailed arms:")
        for arm, reason in failed_arms.items():
            print(f"  {arm}: {reason}")

    # Writing a results file with no scored arm would leave a plausible-looking
    # artefact on disk that report.py would happily render. Fail loudly instead.
    if not results:
        print("\nNo arm produced results — nothing written.")
        return 1

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "retrieval_ablation.json"
    out.write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "top_k": TOP_K,
        "queries": len(queries),
        "corpus": corpus_stats(),
        "arms": results,
        "failed_arms": failed_arms,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", default="guest",
                        help="user whose ingested documents form the corpus")
    parser.add_argument("--arms", default="all",
                        help=f"comma-separated subset of {ARMS}, or 'all'")
    parser.add_argument("--dump-chunks", metavar="QUERY",
                        help="print retrieved chunks for one query, to build the gold set")
    parser.add_argument("--corpus-stats", action="store_true",
                        help="report what is indexed (duplication, files) and exit")
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
