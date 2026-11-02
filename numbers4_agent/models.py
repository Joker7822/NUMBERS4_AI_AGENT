"""Transparent research candidates; historical fit is NOT evidence of skill."""
from __future__ import annotations
from collections import Counter
from hashlib import sha256
from math import log

from .rules import PlayType, validate_play

MODEL_RESEARCH = "positional-dirichlet-research-v1"
MODEL_REFERENCE = "uniform-deterministic-reference-v1"


def ranked_candidates(history: list[dict], target_round: int, *,
                      mode: str = "straight", count: int = 5,
                      method: str = "positional") -> dict:
    if not isinstance(target_round, int) or isinstance(target_round, bool) or target_round < 1:
        raise ValueError("invalid future round")
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 5:
        raise ValueError("request 1-5 candidate numbers")
    if method not in {"uniform", "positional"}:
        raise ValueError("unknown research method")
    mode = PlayType(mode)
    rows = sorted(history, key=lambda r: r["round"])
    if any(r["round"] >= target_round for r in rows):
        raise ValueError("look-ahead detected: history includes the target round")
    if len({r["round"] for r in rows}) != len(rows):
        raise ValueError("duplicate training round")
    for r in rows:
        validate_play(r["winning_number"], "straight")
    recent = rows[-250:]
    use_empirical = method == "positional" and len(recent) >= 30
    probabilities = [[0.1] * 10 for _ in range(4)]
    if use_empirical:
        for pos in range(4):
            counts = Counter(int(r["winning_number"][pos]) for r in recent)
            # Dirichlet(5) shrinks noisy marginal rates toward 10%.
            probabilities[pos] = [(counts[digit] + 5) / (len(recent) + 50) for digit in range(10)]
    label = MODEL_RESEARCH if use_empirical else MODEL_REFERENCE
    seed = sha256((str(target_round) + ":" +
                   ",".join(f'{r["round"]}={r["winning_number"]}' for r in recent)).encode()).hexdigest()

    def score(n: str) -> float:
        return sum(log(probabilities[pos][int(n[pos])]) for pos in range(4))

    def tie_break(n: str) -> bytes:
        return sha256((seed + ":" + n).encode()).digest()

    candidates = [f"{value:04d}" for value in range(10_000)]
    if mode is not PlayType.STRAIGHT:
        candidates = [n for n in candidates if len(set(n)) > 1]
    candidates.sort(key=lambda n: (-score(n), tie_break(n)))
    result = []
    unordered_seen = set()
    for n in candidates:
        signature = "".join(sorted(n)) if mode is not PlayType.STRAIGHT else n
        if signature in unordered_seen:
            continue
        unordered_seen.add(signature)
        result.append(n)
        if len(result) == count:
            break
    return {
        "target_round": target_round, "model_version": label,
        "mode": mode.value, "numbers": result,
        "training_rounds": len(recent), "data_cutoff_round": rows[-1]["round"] if rows else None,
        "confidence": "not_established", "purchase_authorized": False,
        "scope": "research_candidate_only_not_issued",
    }
