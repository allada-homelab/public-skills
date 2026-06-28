import math
from llm_wiki_optimizer.score import prf1, uplift


def test_perfect_match():
    p, r, f = prf1(predicted=["a", "b"], gold=["a", "b"])
    assert (p, r, f) == (1.0, 1.0, 1.0)


def test_partial_with_distractor():
    # predicted a (gold), c (distractor); gold a,b
    p, r, f = prf1(predicted=["a", "c"], gold=["a", "b"])
    assert p == 0.5 and r == 0.5
    assert math.isclose(f, 0.5)


def test_empty_prediction_scores_zero_recall():
    p, r, f = prf1(predicted=[], gold=["a"])
    assert r == 0.0 and f == 0.0


def test_dedup_predicted():
    p, r, f = prf1(predicted=["a", "a"], gold=["a"])
    assert p == 1.0 and r == 1.0


def test_uplift_is_with_minus_ablated():
    assert uplift(with_wiki_f1=0.8, ablated_f1=0.5) == 0.3
