"""Tests for ski_planner.py. Run them from the project folder with ``pytest``."""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import ski_planner  # noqa: E402


def random_problem(n, rng):
    """Small made-up problem with random times, in minutes."""
    return {
        "runs": [{"name": f"run {j}"} for j in range(n)],
        "ski": [rng.uniform(2, 6) for _ in range(n)],
        "from_base": [rng.uniform(5, 15) for _ in range(n)],
        "between": [[0.0 if i == j else rng.uniform(3, 15) for j in range(n)]
                    for i in range(n)],
        "to_base": [rng.uniform(1, 10) for _ in range(n)],
        "base": 0,
    }


def test_exact_matches_brute_force():
    rng = random.Random(1)
    for _ in range(30):
        problem = random_problem(rng.randint(1, 6), rng)
        budget = rng.uniform(10, 80)
        exact = ski_planner.exact_route(problem, budget)
        brute = ski_planner.brute_force_route(problem, budget)
        assert len(exact) == len(brute)
        assert len(set(exact)) == len(exact)
        exact_minutes = ski_planner.route_minutes(problem, exact)
        brute_minutes = ski_planner.route_minutes(problem, brute)
        assert exact_minutes <= budget + 1e-9
        assert abs(exact_minutes - brute_minutes) < 1e-9


def test_greedy_respects_budget_and_never_beats_exact():
    rng = random.Random(2)
    for _ in range(30):
        problem = random_problem(rng.randint(1, 8), rng)
        budget = rng.uniform(10, 120)
        greedy = ski_planner.greedy_route(problem, budget)
        assert len(set(greedy)) == len(greedy)
        assert ski_planner.route_minutes(problem, greedy) <= budget + 1e-9
        assert len(greedy) <= len(ski_planner.exact_route(problem, budget))


def test_budget_too_small():
    problem = random_problem(3, random.Random(3))
    assert ski_planner.exact_route(problem, 1) == []
    assert ski_planner.greedy_route(problem, 1) == []