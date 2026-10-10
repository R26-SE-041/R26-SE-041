"""Evaluation metrics for the VoiceLearn baseline comparison.

Pure standard library on purpose. The evaluation must be re-runnable from the
saved raw outputs long after the Modal endpoints are torn down, on a machine
with no GPU and no `jiwer`/`sacrebleu`/`ragas` install — and a reviewer must be
able to read exactly how each number was produced. Every function here is the
textbook definition, with the tokenisation choices spelled out because for
Tamil and Sinhala those choices change the numbers.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from typing import Iterable, Sequence

# ── text normalisation ───────────────────────────────────────────────────────

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+", re.UNICODE)


def normalise(text: str, *, drop_punct: bool = True, casefold: bool = True) -> str:
    """Normalise a transcript before scoring.

    NFC first: Tamil and Sinhala combining marks have several valid encodings,
    and an unnormalised reference/hypothesis pair can differ by zero visible
    characters yet score a non-zero CER. Report that this was applied — WER on
    Indic scripts is not comparable across papers without it.
    """
    text = unicodedata.normalize("NFC", text or "")
    if casefold:
        text = text.casefold()
    if drop_punct:
        text = _PUNCT_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


# ── edit distance ────────────────────────────────────────────────────────────

def _levenshtein(ref: Sequence, hyp: Sequence) -> tuple[int, int, int, int]:
    """Return (substitutions, deletions, insertions, distance).

    Two-row dynamic programme with a backtrace-free operation count: each cell
    carries the running S/D/I tally of the cheapest path reaching it, which is
    all the error breakdown a WER table needs.
    """
    prev = [(j, 0, 0, j) for j in range(len(hyp) + 1)]  # (dist, S, D, I)
    for i in range(1, len(ref) + 1):
        cur = [(i, 0, i, 0)]
        for j in range(1, len(hyp) + 1):
            if ref[i - 1] == hyp[j - 1]:
                d, s, dl, ins = prev[j - 1]
                cur.append((d, s, dl, ins))
                continue
            sub_d, sub_s, sub_dl, sub_i = prev[j - 1]
            del_d, del_s, del_dl, del_i = prev[j]
            ins_d, ins_s, ins_dl, ins_i = cur[j - 1]
            best = min(
                (sub_d + 1, sub_s + 1, sub_dl, sub_i),
                (del_d + 1, del_s, del_dl + 1, del_i),
                (ins_d + 1, ins_s, ins_dl, ins_i + 1),
                key=lambda t: t[0],
            )
            cur.append(best)
        prev = cur
    dist, subs, dels, ins = prev[-1]
    return subs, dels, ins, dist


def wer(reference: str, hypothesis: str, **norm_kwargs) -> dict[str, float]:
    """Word error rate with its S/D/I breakdown.

    Word-level WER is the wrong headline metric for Sinhala and Tamil on its
    own — both are agglutinative, so one wrong morpheme condemns a whole word.
    Report WER alongside CER; a large WER/CER gap is itself a finding about
    morphological rather than acoustic error.
    """
    ref = normalise(reference, **norm_kwargs).split()
    hyp = normalise(hypothesis, **norm_kwargs).split()
    if not ref:
        return {"wer": 0.0 if not hyp else 1.0, "sub": 0, "del": 0, "ins": len(hyp), "ref_len": 0}
    subs, dels, ins, dist = _levenshtein(ref, hyp)
    return {
        "wer": dist / len(ref),
        "sub": subs, "del": dels, "ins": ins,
        "ref_len": len(ref),
    }


def cer(reference: str, hypothesis: str, **norm_kwargs) -> dict[str, float]:
    """Character error rate — the primary ASR metric for Tamil/Sinhala here."""
    ref = normalise(reference, **norm_kwargs).replace(" ", "")
    hyp = normalise(hypothesis, **norm_kwargs).replace(" ", "")
    if not ref:
        return {"cer": 0.0 if not hyp else 1.0, "ref_len": 0}
    subs, dels, ins, dist = _levenshtein(ref, hyp)
    return {"cer": dist / len(ref), "sub": subs, "del": dels, "ins": ins, "ref_len": len(ref)}


def corpus_wer(pairs: Iterable[tuple[str, str]], **norm_kwargs) -> dict[str, float]:
    """Corpus WER = total edits / total reference words.

    NOT the mean of per-utterance WERs. Averaging per-utterance rates lets a
    three-word utterance outvote a thirty-word one; the pooled ratio is the
    standard and is what ASR leaderboards report.
    """
    tot_dist = tot_ref = tot_s = tot_d = tot_i = 0
    for reference, hypothesis in pairs:
        ref = normalise(reference, **norm_kwargs).split()
        hyp = normalise(hypothesis, **norm_kwargs).split()
        subs, dels, ins, dist = _levenshtein(ref, hyp)
        tot_dist += dist
        tot_ref += len(ref)
        tot_s += subs
        tot_d += dels
        tot_i += ins
    return {
        "wer": tot_dist / tot_ref if tot_ref else 0.0,
        "sub": tot_s, "del": tot_d, "ins": tot_i,
        "ref_words": tot_ref,
    }


def corpus_cer(pairs: Iterable[tuple[str, str]], **norm_kwargs) -> dict[str, float]:
    tot_dist = tot_ref = 0
    for reference, hypothesis in pairs:
        ref = normalise(reference, **norm_kwargs).replace(" ", "")
        hyp = normalise(hypothesis, **norm_kwargs).replace(" ", "")
        _, _, _, dist = _levenshtein(ref, hyp)
        tot_dist += dist
        tot_ref += len(ref)
    return {"cer": tot_dist / tot_ref if tot_ref else 0.0, "ref_chars": tot_ref}


# ── script-purity (this system's specific ASR/TTS failure mode) ──────────────

def native_script_ratio(text: str, script: str) -> float:
    """Fraction of letters that belong to the expected script.

    Whisper's documented failure on Tamil and Sinhala is romanisation — emitting
    "Night" for "நாய்". `whisper_stt.py` fights it with an ASCII suppress list,
    so the paper needs a number showing whether that worked. Plain WER cannot
    show it: a fully romanised transcript and a garbled native one can score
    the same.
    """
    ranges = {
        "tamil": ((0x0B80, 0x0BFF),),
        "sinhala": ((0x0D80, 0x0DFF),),
        "latin": ((0x0041, 0x024F),),
    }[script]
    letters = [c for c in unicodedata.normalize("NFC", text or "") if c.isalpha()]
    if not letters:
        return 0.0
    hits = sum(1 for c in letters if any(lo <= ord(c) <= hi for lo, hi in ranges))
    return hits / len(letters)


# ── retrieval ────────────────────────────────────────────────────────────────

def recall_at_k(ranked_ids: Sequence[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    return len(set(ranked_ids[:k]) & relevant_ids) / len(relevant_ids)


def hit_at_k(ranked_ids: Sequence[str], relevant_ids: set[str], k: int) -> float:
    """1.0 if any gold chunk made the top k. For a RAG feed this is often the
    metric that actually predicts answer quality — the generator only needs the
    evidence to be present, not perfectly ordered."""
    return 1.0 if set(ranked_ids[:k]) & relevant_ids else 0.0


def reciprocal_rank(ranked_ids: Sequence[str], relevant_ids: set[str]) -> float:
    for rank, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranked_ids: Sequence[str], relevant_ids: set[str], k: int) -> float:
    """Binary-gain nDCG@k — rewards putting gold chunks near the top.

    This is the metric that separates "reranker helped" from "reranker did
    nothing": recall@k is blind to ordering, and the reranker's entire job is
    ordering.
    """
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, doc_id in enumerate(ranked_ids[:k], start=1)
        if doc_id in relevant_ids
    )
    ideal = sum(1.0 / math.log2(r + 1) for r in range(1, min(len(relevant_ids), k) + 1))
    return dcg / ideal if ideal else 0.0


def retrieval_report(
    runs: Iterable[tuple[Sequence[str], set[str]]],
    ks: Sequence[int] = (1, 3, 5, 10),
) -> dict[str, float]:
    """Mean retrieval metrics across a query set."""
    runs = list(runs)
    if not runs:
        return {}
    out: dict[str, float] = {"queries": len(runs)}
    for k in ks:
        out[f"recall@{k}"] = round(sum(recall_at_k(r, g, k) for r, g in runs) / len(runs), 4)
        out[f"hit@{k}"] = round(sum(hit_at_k(r, g, k) for r, g in runs) / len(runs), 4)
        out[f"ndcg@{k}"] = round(sum(ndcg_at_k(r, g, k) for r, g in runs) / len(runs), 4)
    out["mrr"] = round(sum(reciprocal_rank(r, g) for r, g in runs) / len(runs), 4)
    return out


# ── translation / localisation ───────────────────────────────────────────────

def _ngrams(tokens: Sequence[str], n: int) -> Counter:
    return Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))


def bleu(references: Sequence[str], hypotheses: Sequence[str], max_n: int = 4) -> float:
    """Corpus BLEU-4 with the standard brevity penalty.

    Caveat worth stating in the paper: BLEU is weak on Tamil and Sinhala
    because whitespace tokenisation splits agglutinative words badly. chrF is
    the more trustworthy of the two here — report both, and lead with chrF.
    """
    clipped = [0] * max_n
    totals = [0] * max_n
    ref_len = hyp_len = 0
    for reference, hypothesis in zip(references, hypotheses):
        ref_tokens = normalise(reference).split()
        hyp_tokens = normalise(hypothesis).split()
        ref_len += len(ref_tokens)
        hyp_len += len(hyp_tokens)
        for n in range(1, max_n + 1):
            ref_counts = _ngrams(ref_tokens, n)
            hyp_counts = _ngrams(hyp_tokens, n)
            totals[n - 1] += max(sum(hyp_counts.values()), 0)
            clipped[n - 1] += sum(min(c, ref_counts[g]) for g, c in hyp_counts.items())
    if not hyp_len or any(t == 0 for t in totals):
        return 0.0
    precisions = [c / t if t else 0.0 for c, t in zip(clipped, totals)]
    if any(p == 0 for p in precisions):
        return 0.0
    geo_mean = math.exp(sum(math.log(p) for p in precisions) / max_n)
    brevity = 1.0 if hyp_len > ref_len else math.exp(1 - ref_len / hyp_len)
    return round(100 * brevity * geo_mean, 2)


def chrf(reference: str, hypothesis: str, n: int = 6, beta: float = 2.0) -> float:
    """chrF++ style character n-gram F-score (beta=2 favours recall).

    Character-level, so it is script-aware and tokenisation-free — the right
    default for Tamil/Sinhala where BLEU's word assumption breaks down.
    """
    ref = normalise(reference).replace(" ", "")
    hyp = normalise(hypothesis).replace(" ", "")
    if not ref or not hyp:
        return 0.0
    precisions, recalls = [], []
    for order in range(1, n + 1):
        ref_grams = _ngrams(ref, order)
        hyp_grams = _ngrams(hyp, order)
        overlap = sum(min(c, ref_grams[g]) for g, c in hyp_grams.items())
        hyp_total = sum(hyp_grams.values())
        ref_total = sum(ref_grams.values())
        if hyp_total:
            precisions.append(overlap / hyp_total)
        if ref_total:
            recalls.append(overlap / ref_total)
    if not precisions or not recalls:
        return 0.0
    p = sum(precisions) / len(precisions)
    r = sum(recalls) / len(recalls)
    if p + r == 0:
        return 0.0
    b2 = beta ** 2
    return round(100 * (1 + b2) * p * r / (b2 * p + r), 2)


def corpus_chrf(references: Sequence[str], hypotheses: Sequence[str]) -> float:
    scores = [chrf(r, h) for r, h in zip(references, hypotheses)]
    return round(sum(scores) / len(scores), 2) if scores else 0.0


# ── generation quality ───────────────────────────────────────────────────────

def rouge_l(reference: str, hypothesis: str) -> dict[str, float]:
    """ROUGE-L via longest common subsequence, F1 with beta=1."""
    ref = normalise(reference).split()
    hyp = normalise(hypothesis).split()
    if not ref or not hyp:
        return {"p": 0.0, "r": 0.0, "f1": 0.0}
    prev = [0] * (len(hyp) + 1)
    for a in ref:
        cur = [0]
        for j, b in enumerate(hyp, start=1):
            cur.append(prev[j - 1] + 1 if a == b else max(prev[j], cur[j - 1]))
        prev = cur
    lcs = prev[-1]
    p = lcs / len(hyp)
    r = lcs / len(ref)
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"p": round(p, 4), "r": round(r, 4), "f1": round(f1, 4)}


def token_f1(reference: str, hypothesis: str) -> float:
    """Bag-of-words F1 — the SQuAD-style answer-overlap score."""
    ref = Counter(normalise(reference).split())
    hyp = Counter(normalise(hypothesis).split())
    overlap = sum((ref & hyp).values())
    if not overlap:
        return 0.0
    p = overlap / sum(hyp.values())
    r = overlap / sum(ref.values())
    return round(2 * p * r / (p + r), 4)


def context_groundedness(answer: str, context_chunks: Sequence[str]) -> float:
    """Fraction of the answer's content words that appear in the retrieved context.

    A cheap, deterministic, zero-credit proxy for RAGAS faithfulness. It is a
    lower bound, not a substitute: paraphrase is penalised. Use it to *screen*
    for hallucination across the whole set, then hand the low-scoring tail to
    the LLM-judge or a human. Say exactly this in the paper — a reviewer will
    otherwise read it as a faithfulness claim it cannot support.
    """
    context_tokens = set()
    for chunk in context_chunks:
        context_tokens |= set(normalise(chunk).split())
    answer_tokens = [t for t in normalise(answer).split() if len(t) > 3]
    if not answer_tokens:
        return 0.0
    return round(sum(1 for t in answer_tokens if t in context_tokens) / len(answer_tokens), 4)


# ── classification (router) ──────────────────────────────────────────────────

def classification_report(
    gold: Sequence[str],
    predicted: Sequence[str],
    labels: Sequence[str] | None = None,
) -> dict:
    """Per-label precision/recall/F1 plus macro average and a confusion matrix."""
    labels = list(labels or sorted(set(gold) | set(predicted)))
    matrix = {g: Counter() for g in labels}
    for g, p in zip(gold, predicted):
        matrix[g][p] += 1

    per_label = {}
    for label in labels:
        tp = matrix[label][label]
        fp = sum(matrix[g][label] for g in labels if g != label)
        fn = sum(matrix[label][p] for p in labels if p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": sum(matrix[label].values()),
        }

    correct = sum(matrix[label][label] for label in labels)
    total = len(gold)
    return {
        "accuracy": round(correct / total, 4) if total else 0.0,
        "macro_f1": round(sum(v["f1"] for v in per_label.values()) / len(labels), 4),
        "per_label": per_label,
        "confusion": {g: dict(matrix[g]) for g in labels},
        "n": total,
    }


# ── uncertainty ──────────────────────────────────────────────────────────────

def bootstrap_ci(
    values: Sequence[float],
    iterations: int = 2000,
    confidence: float = 0.95,
    seed: int = 20260903,
) -> tuple[float, float]:
    """Percentile bootstrap CI for a mean.

    Include this on every headline metric. A WER difference of 2 points on 100
    utterances is usually inside the interval, and a table without CIs invites
    exactly that over-claim from a reviewer.
    """
    import random

    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(iterations):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int((1 - confidence) / 2 * iterations)]
    hi = means[min(iterations - 1, int((1 + confidence) / 2 * iterations))]
    return (round(lo, 4), round(hi, 4))
