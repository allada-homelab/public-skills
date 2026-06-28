from __future__ import annotations


def prf1(predicted: list[str], gold: list[str]) -> tuple[float, float, float]:
    """Set precision/recall/F1 over symbol identities (order-unaware, deduped)."""
    p_set, g_set = set(predicted), set(gold)
    if not p_set and not g_set:
        return 1.0, 1.0, 1.0
    tp = len(p_set & g_set)
    precision = tp / len(p_set) if p_set else 0.0
    recall = tp / len(g_set) if g_set else 0.0
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def uplift(with_wiki_f1: float, ablated_f1: float) -> float:
    """Per-item uplift: what the wiki adds over the same agent without it."""
    return round(with_wiki_f1 - ablated_f1, 10)
