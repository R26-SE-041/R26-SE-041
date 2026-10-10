"""Turn the saved benchmark JSON into paper-ready Markdown and LaTeX tables.

Reads only from `benchmarks/results/`, never from the network, so tables can be
regenerated and reformatted any number of times without touching Modal. Every
section renders only if its result file exists, so this is safe to run at any
point during a partially-complete study.

Usage:
    python -m benchmarks.report                    # everything available
    python -m benchmarks.report --only latency,router
    python -m benchmarks.report --latex
    python -m benchmarks.report --results results_run2 --out tables_run2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

BENCH_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BENCH_DIR / "results"
OUT_DIR = BENCH_DIR / "tables"

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


# ── formatting helpers ───────────────────────────────────────────────────────

def _latex_escape(text: str) -> str:
    for char, repl in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
                       ("_", r"\_"), ("#", r"\#"), ("{", r"\{"), ("}", r"\}")]:
        text = text.replace(char, repl)
    return text


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def latex_table(headers: list[str], rows: list[list[str]], caption: str, label: str) -> str:
    align = "l" + "r" * (len(headers) - 1)
    lines = [
        r"\begin{table}[t]", r"\centering", r"\small",
        rf"\begin{{tabular}}{{{align}}}", r"\toprule",
        " & ".join(_latex_escape(h) for h in headers) + r" \\", r"\midrule",
    ]
    lines += [" & ".join(_latex_escape(c) for c in r) + r" \\" for r in rows]
    lines += [r"\bottomrule", r"\end{tabular}",
              rf"\caption{{{caption}}}", rf"\label{{{label}}}", r"\end{table}"]
    return "\n".join(lines)


def load(name: str) -> Any | None:
    path = RESULTS_DIR / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def set_results_dir(path: Path) -> None:
    """Point every section at a different result set.

    Keeps the renderer testable without fabricating files inside the real
    results directory, and lets several measurement runs be kept side by side
    and re-rendered independently.
    """
    global RESULTS_DIR
    RESULTS_DIR = path


def fmt(value: Any, spec: str = ".3f", dash: str = "—") -> str:
    """Format a number, or an em dash when the metric was not computed.

    Missing metrics are common and meaningful here — round-trip CER is absent
    until the transcription pass runs, term preservation is absent when a case
    listed no required terms — so they must render as clearly absent rather
    than as zero.
    """
    if value is None:
        return dash
    if isinstance(value, (int, float)):
        return format(value, spec)
    return str(value)


def ci(pair: Any) -> str:
    if not pair or not isinstance(pair, (list, tuple)) or len(pair) != 2:
        return ""
    return f" [{pair[0]:.3f}, {pair[1]:.3f}]"


# ── 1. warm-state latency ────────────────────────────────────────────────────

def latency_section(latex: bool) -> str | None:
    records = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(RESULTS_DIR.glob("latency_*.json"))
        if not p.name.startswith("latency_all_")
    ]
    if not records:
        return None

    headers = ["Agent / stage", "Model", "GPU (device)", "p50 (ms)",
               "p95 (ms)", "mean ± sd (ms)", "RTF", "n"]
    rows = []
    for rec in sorted(records, key=lambda r: r["stage"]):
        wall = rec.get("wall", {})
        gpu = rec.get("gpu_info", {})
        device = gpu.get("gpu_name") or f"{rec['requested_gpu']} (not probed)"
        if gpu.get("vram_total_gb"):
            device = f"{device} ({gpu['vram_total_gb']} GB)"
        mean_sd = (f"{wall.get('mean_ms', 0):.0f} ± {wall.get('sd_ms', 0):.0f}"
                   if wall else "—")
        flag = "" if rec.get("warm_state_valid", True) else " †"
        rows.append([
            rec["stage"] + flag, rec["model_id"], device,
            fmt(wall.get("p50_ms"), ".0f"), fmt(wall.get("p95_ms"), ".0f"),
            mean_sd, fmt(rec.get("rtf"), ".2f"), str(wall.get("n", 0)),
        ])

    parts = ["## Table 1 — Warm-state inference latency and serving hardware\n",
             md_table(headers, rows), ""]

    invalid = [r for r in records if not r.get("warm_state_valid", True)]
    if invalid:
        parts.append("† Batch exceeded the container's `scaledown_window`; a cold "
                     "start may have occurred mid-run. Re-measure before publishing:\n")
        parts += [f"  - `{r['key']}`: {r.get('warning', '')}" for r in invalid]
        parts.append("")

    with_server = [r for r in records if r.get("server")]
    if with_server:
        parts.append("\n## Table 2 — Compute time vs. platform overhead\n")
        sub_rows = []
        for rec in sorted(with_server, key=lambda r: r["stage"]):
            wall_p50, srv_p50 = rec["wall"]["p50_ms"], rec["server"]["p50_ms"]
            sub_rows.append([
                rec["stage"], f"{srv_p50:.0f}", f"{wall_p50:.0f}",
                f"{wall_p50 - srv_p50:.0f}",
                f"{(wall_p50 - srv_p50) / wall_p50 * 100:.1f}%",
            ])
        parts.append(md_table(
            ["Agent / stage", "Server compute p50 (ms)", "End-to-end p50 (ms)",
             "Overhead (ms)", "Overhead share"], sub_rows))
        parts.append(
            "\nOverhead is TLS, Modal's request routing and JSON/audio transfer. "
            "It is the cost of serverless GPU hosting rather than of the model, "
            "and is what a self-hosted deployment would remove.\n")

    parts.append("\n## Table 3 — Requested GPU class vs. scheduled device\n")
    parts.append(md_table(
        ["Agent", "Requested (`@app.cls(gpu=…)`)", "Reported device", "Source"],
        [[r["key"], r["requested_gpu"],
          r.get("gpu_info", {}).get("gpu_name", "not probed"), r["source"]]
         for r in sorted(records, key=lambda r: r["key"])]))

    if latex:
        parts.append("\n\n% ── LaTeX ──\n")
        parts.append(latex_table(
            headers, rows,
            "Warm-state inference latency and serving hardware for each agent. "
            "Cold starts excluded; $n$ requests issued back-to-back after a "
            "discarded warm-up.", "tab:latency"))
    return "\n".join(parts)


# ── 2. ASR ───────────────────────────────────────────────────────────────────

def asr_section(latex: bool) -> str | None:
    data = load("asr_eval.json")
    if not data:
        return None

    headers = ["System", "Language", "WER", "CER", "CER 95% CI",
               "Native script", "RTF", "n"]
    rows = []
    for report in data["reports"]:
        for language, m in report["languages"].items():
            rows.append([
                report["label"], language,
                fmt(m["corpus_wer"]), fmt(m["corpus_cer"]),
                ci(m.get("cer_ci95")).strip() or "—",
                fmt(m.get("native_script_ratio")),
                fmt(m.get("rtf_mean"), ".2f"), str(m["n"]),
            ])

    parts = [
        "## Table 4 — ASR baseline comparison\n",
        md_table(headers, rows),
        f"\nNormalisation: {data.get('normalisation', 'see metrics.py')}. "
        "Corpus WER and CER are total edits ÷ total reference units, not the "
        "mean of per-utterance rates.\n",
        "**CER leads for Tamil and Sinhala.** Both are agglutinative, so one "
        "wrong morpheme condemns a whole word and WER overstates what a reader "
        "actually loses. A wide WER/CER gap is itself a finding about "
        "morphological rather than acoustic error.\n",
        "**Native script** is the fraction of output letters in the expected "
        "script. It detects romanisation — Whisper emitting \"Night\" for "
        "\"நாய்\" — which WER cannot distinguish from ordinary garbling.\n",
    ]
    if latex:
        parts.append("\n% ── LaTeX ──\n")
        parts.append(latex_table(headers, rows,
                                 "ASR word and character error rates by system "
                                 "and language.", "tab:asr"))
    return "\n".join(parts)


# ── 3. TTS ───────────────────────────────────────────────────────────────────

def tts_section(latex: bool) -> str | None:
    data = load("tts_eval.json")
    if not data:
        return None

    headers = ["System", "Language", "Round-trip CER", "Native script",
               "RTF", "Mean audio (s)", "Latency (ms)", "n"]
    rows = []
    for report in data["reports"]:
        for language, m in report["languages"].items():
            rows.append([
                report["label"], language,
                fmt(m.get("roundtrip_cer")), fmt(m.get("roundtrip_script_ratio")),
                fmt(m.get("rtf_mean"), ".2f"), fmt(m.get("mean_audio_seconds"), ".1f"),
                fmt(m.get("mean_latency_ms"), ".0f"), str(m["n"]),
            ])

    parts = [
        "## Table 5 — TTS objective comparison\n",
        md_table(headers, rows),
        f"\n{data.get('caveat', '')}\n",
        "RTF is wall-clock ÷ generated audio seconds; below 1.0 means the model "
        "synthesises faster than real time. The CPU-served Kokoro row against "
        "the GPU-served rows is a deployment-economics result in its own right.\n",
        "_The naturalness claim rests on the MOS study, not this table. Report "
        "mean MOS with 95% CI per system and inter-rater agreement alongside it._\n",
    ]
    if latex:
        parts.append("\n% ── LaTeX ──\n")
        parts.append(latex_table(headers, rows,
                                 "TTS round-trip intelligibility and real-time "
                                 "factor.", "tab:tts"))
    return "\n".join(parts)


# ── 4. retrieval ─────────────────────────────────────────────────────────────

def retrieval_section(latex: bool) -> str | None:
    data = load("retrieval_ablation.json")
    if not data:
        return None

    order = ["bm25", "dense", "hybrid", "reranked"]
    labels = {
        "bm25": "BM25 (sparse only)",
        "dense": "BGE-M3 dense",
        "hybrid": "Hybrid + RRF",
        "reranked": "Hybrid + RRF + BGE reranker",
    }
    headers = ["Arm", "R@1", "R@5", "R@10", "nDCG@10", "MRR",
               "R@5 95% CI", "Latency (ms)"]
    rows = []
    for arm in order:
        if arm not in data["arms"]:
            continue
        m = data["arms"][arm]["metrics"]
        rows.append([
            labels[arm],
            fmt(m.get("recall@1")), fmt(m.get("recall@5")), fmt(m.get("recall@10")),
            fmt(m.get("ndcg@10")), fmt(m.get("mrr")),
            ci(m.get("recall@5_ci95")).strip() or "—",
            fmt(m.get("latency_ms_mean"), ".0f"),
        ])

    parts = [
        "## Table 6 — Retrieval ablation\n",
        f"{data['queries']} annotated queries, top-{data['top_k']} retrieved.\n",
        md_table(headers, rows),
        "\nRead nDCG and MRR, not recall alone, when judging the reranker. "
        "Recall@k is order-blind and the reranker only reorders, so a "
        "recall-only comparison makes it look inert no matter how well it "
        "works — the gain shows up in the ranking metrics.\n",
    ]
    if latex:
        parts.append("\n% ── LaTeX ──\n")
        parts.append(latex_table(headers, rows,
                                 "Retrieval ablation over the deployed pipeline.",
                                 "tab:retrieval"))
    return "\n".join(parts)


# ── 5. generation ────────────────────────────────────────────────────────────

def generation_section(latex: bool) -> str | None:
    data = load("generation_eval.json")
    if not data:
        return None

    split_labels = {
        "overall": "all questions",
        "in_finetune_domain": "five trained muscles",
        "out_of_domain": "outside the fine-tune",
    }
    headers = ["System", "Split", "ROUGE-L F1", "Token F1", "Groundedness",
               "Latency (ms)", "Answer words", "n"]
    rows = []
    for report in data["reports"]:
        for split, label in split_labels.items():
            m = report.get(split)
            if not m:
                continue
            rows.append([
                report["label"], label,
                fmt(m.get("rouge_l_f1")), fmt(m.get("token_f1")),
                fmt(m.get("context_groundedness")),
                fmt(m.get("mean_latency_ms"), ".0f"),
                fmt(m.get("mean_answer_words"), ".0f"), str(m["n"]),
            ])

    parts = [
        "## Table 7 — Answer generation: base vs. fine-tuned vs. RAG\n",
        md_table(headers, rows),
        "\n**Read the split rows, not the pooled row.** The claim the fine-tune "
        "has to support is an interaction: it should beat the base model on the "
        "five trained muscles *without regressing outside them*. A pooled "
        "average hides both halves of that.\n",
        f"\n_{data.get('caveat', '')}_\n",
    ]
    if latex:
        parts.append("\n% ── LaTeX ──\n")
        parts.append(latex_table(headers, rows,
                                 "Answer-generation quality by system and "
                                 "fine-tune domain.", "tab:generation"))
    return "\n".join(parts)


# ── 6. localisation ──────────────────────────────────────────────────────────

def localization_section(latex: bool) -> str | None:
    data = load("localization_eval.json")
    if not data:
        return None

    headers = ["System", "Language", "chrF", "chrF 95% CI", "BLEU",
               "Term preservation", "Native script", "Latency (ms)", "n"]
    rows = []
    for report in data["reports"]:
        for language, m in report["languages"].items():
            rows.append([
                report["label"], language,
                fmt(m.get("chrf"), ".2f"), ci(m.get("chrf_ci95")).strip() or "—",
                fmt(m.get("bleu"), ".2f"), fmt(m.get("term_preservation")),
                fmt(m.get("native_script_ratio")),
                fmt(m.get("mean_latency_ms"), ".0f"), str(m["n"]),
            ])

    parts = [
        "## Table 8 — Localisation (en→ta / en→si)\n",
        md_table(headers, rows),
        "\n**chrF leads, BLEU is reported for comparability only.** BLEU "
        "tokenises on whitespace, and a correct Tamil or Sinhala translation "
        "that inflects a word differently scores near zero on 4-gram precision "
        "while remaining perfectly readable.\n",
        "**Term preservation** is the fraction of required anatomical terms that "
        "survived translation — the metric that matters for a tutoring system, "
        "since a fluent answer that loses the nomenclature has failed the "
        "student. Never read it alone: the copy-through row scores a perfect "
        "1.000 precisely because it does not translate, so term preservation is "
        "only meaningful once chrF and native script confirm that translation "
        "actually happened.\n",
        "**Native script** doubles as a failure detector: `call_localizer` "
        "returns the original English on any error, so a silent failure looks "
        "like a successful call and only the script check catches it. The "
        "copy-through baseline row makes that floor explicit.\n",
    ]
    if latex:
        parts.append("\n% ── LaTeX ──\n")
        parts.append(latex_table(headers, rows,
                                 "Localisation quality for English to Tamil and "
                                 "Sinhala.", "tab:localization"))
    return "\n".join(parts)


# ── 7. end-to-end ────────────────────────────────────────────────────────────

def e2e_section(latex: bool) -> str | None:
    data = load("e2e_latency.json")
    if not data:
        return None

    stages = ["stt", "prompt_enhancer", "rag", "localization", "tts"]
    stage_names = {
        "stt": "STT", "prompt_enhancer": "Correction", "rag": "RAG",
        "localization": "Localisation", "tts": "TTS",
    }
    headers = (["Language", "Turn p50 (ms)", "Turn mean ± sd (ms)"]
               + [stage_names[s] for s in stages] + ["Other", "n"])
    rows = []
    for rec in data["languages"]:
        total = rec.get("total_ms")
        if not total:
            continue
        cells = []
        for stage in stages:
            info = rec.get("stages", {}).get(stage)
            cells.append(f"{info['mean_ms']:.0f} ({info['share_pct']:.0f}%)"
                         if info else "—")
        rows.append([
            rec["language"], f"{total['p50']:.0f}",
            f"{total['mean']:.0f} ± {total['sd']:.0f}", *cells,
            f"{rec.get('unaccounted_ms', 0):.0f} "
            f"({rec.get('unaccounted_pct', 0):.0f}%)",
            str(total["n"]),
        ])

    parts = [
        "## Table 9 — End-to-end turn latency and stage breakdown\n",
        md_table(headers, rows),
        f"\n{data.get('scope', '')}\n",
        "\nStage times are measured inside the compiled graph, not summed from "
        "Table 1. *Other* is what the five nodes do not account for: retrieval "
        "and Chroma access, the Supabase audio upload inside the TTS node, and "
        "the graph's own overhead.\n",
        "\nThe language rows are not comparable as a single average — each "
        "exercises a different set of models:\n",
    ]
    parts += [f"  - **{r['language']}**: {r['model_path']}" for r in data["languages"]]
    parts.append("")

    if latex:
        parts.append("\n% ── LaTeX ──\n")
        parts.append(latex_table(headers, rows,
                                 "End-to-end spoken-turn latency with per-stage "
                                 "breakdown, by language path.", "tab:e2e"))
    return "\n".join(parts)


# ── 8. router ────────────────────────────────────────────────────────────────

def router_section(latex: bool) -> str | None:
    data = load("router_eval.json")
    if not data:
        return None
    before = load("router_eval_before.json")

    headers = ["Route", "Precision", "Recall", "F1", "Support"]
    rows = [[route, fmt(v["precision"]), fmt(v["recall"]), fmt(v["f1"]),
             str(v["support"])]
            for route, v in data["overall"]["per_label"].items()]

    parts = [
        "## Table 10 — Answer-router accuracy (deterministic, CPU-only)\n",
        f"Overall accuracy **{data['overall']['accuracy']:.3f}**, macro-F1 "
        f"**{data['overall']['macro_f1']:.3f}** over {data['overall']['n']} "
        f"labelled queries.\n",
        md_table(headers, rows),
        "",
        "### Accuracy by query category\n",
        md_table(["Category", "Accuracy", "Errors", "n"],
                 [[cat, fmt(v["accuracy"]), str(v["errors"]), str(v["n"])]
                  for cat, v in data["by_category"].items()]),
        "",
        f"Over-routing onto a paid A100-80GB path: "
        f"**{data['over_routing_to_paid_path']}** of {data['overall']['n']} "
        f"({data['over_routing_to_paid_path'] / data['overall']['n'] * 100:.1f}%). "
        f"Under-routing away from the fine-tuned adapter: "
        f"**{data['under_routing_from_finetune']}**.\n",
    ]

    if before:
        n = before["overall"]["n"]
        parts += [
            "\n### Before and after the routing fixes\n",
            md_table(
                ["Metric", "Before", "After"],
                [
                    ["Accuracy", fmt(before["overall"]["accuracy"]),
                     fmt(data["overall"]["accuracy"])],
                    ["Macro-F1", fmt(before["overall"]["macro_f1"]),
                     fmt(data["overall"]["macro_f1"])],
                    ["`muscle_finetuned_v2` precision",
                     fmt(before["overall"]["per_label"]["muscle_finetuned_v2"]["precision"]),
                     fmt(data["overall"]["per_label"]["muscle_finetuned_v2"]["precision"])],
                    ["Over-routing onto a paid A100 path",
                     f"{before['over_routing_to_paid_path']} / {n} "
                     f"({before['over_routing_to_paid_path'] / n * 100:.1f}%)",
                     f"{data['over_routing_to_paid_path']} / {n} "
                     f"({data['over_routing_to_paid_path'] / n * 100:.1f}%)"],
                    ["Under-routing away from the fine-tune",
                     str(before["under_routing_from_finetune"]),
                     str(data["under_routing_from_finetune"])],
                ]),
            "\n**In-sample caveat.** The same labelled set both revealed these "
            "defects and validated the fix, so the *after* column is optimistic. "
            "Present the delta as evidence that the defects were real; validate "
            "on a held-out set written by someone who has not seen the "
            "implementation before quoting a headline accuracy.\n",
        ]

    if latex:
        parts.append("\n% ── LaTeX ──\n")
        parts.append(latex_table(headers, rows,
                                 "Routing accuracy of the deterministic answer "
                                 "router.", "tab:router"))
    return "\n".join(parts)


SECTIONS: dict[str, Callable[[bool], str | None]] = {
    "latency": latency_section,
    "asr": asr_section,
    "tts": tts_section,
    "retrieval": retrieval_section,
    "generation": generation_section,
    "localization": localization_section,
    "e2e": e2e_section,
    "router": router_section,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", default="all",
                        help=f"comma-separated subset of {list(SECTIONS)}, or 'all'")
    parser.add_argument("--latex", action="store_true", help="also emit LaTeX")
    parser.add_argument("--results", default=str(RESULTS_DIR),
                        help="directory holding the saved result JSON")
    parser.add_argument("--out", default=str(OUT_DIR))
    args = parser.parse_args()

    set_results_dir(Path(args.results))

    wanted = (list(SECTIONS) if args.only == "all"
              else [s.strip() for s in args.only.split(",")])

    rendered, missing = [], []
    for name in wanted:
        if name not in SECTIONS:
            print(f"unknown section: {name}", file=sys.stderr)
            return 2
        section = SECTIONS[name](args.latex)
        if section:
            rendered.append(section)
        else:
            missing.append(name)

    if not rendered:
        print("No results found yet. Start with:\n"
              "  python -m benchmarks.eval_router\n"
              "  python -m benchmarks.latency_bench --agents all")
        return 1

    document = "\n\n---\n\n".join(rendered)
    print(document)

    if missing:
        print(f"\n\n<!-- not yet measured: {', '.join(missing)} -->")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "benchmark_tables.md"
    target.write_text(document + "\n", encoding="utf-8")
    print(f"\n\nwrote {target}")
    if missing:
        print(f"not yet measured: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
