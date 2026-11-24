"""
ski_planner.py
====================================
Finds the route that skis the most different runs
within a time budget. Contains the exact dynamic
programming algorithm, the greedy heuristic and the
genetic algorithm.

| Author: Adrien Diaz
| Date: 2026 November 23
"""

import itertools
import math
import time

import numpy as np

import ski_data
import ski_graph

#: Lift at the bottom of which the day starts and ends.
BASE_LIFT = "Sud"


def make_problem(graph, base):
    """Everything the planning algorithms need, in a small table.

    Runs that cannot be reached from the base, or from which the base
    cannot be reached, are left out.

    Parameters
    ----------
    graph : ski_graph.SkiGraph
        The graph of the ski area.
    base : int
        Node where the day starts and ends.

    Returns
    -------
    dict
        With the keys ``runs`` (list of runs from
        :func:`ski_graph.target_runs`), ``ski`` (minutes to ski each run),
        ``from_base``, ``between`` and ``to_base`` (travel times from
        :func:`ski_graph.travel_times`), and ``base``.
    """
    runs = ski_graph.target_runs(graph)
    from_base, between, to_base = ski_graph.travel_times(graph, runs, base)
    keep = [j for j in range(len(runs))
            if from_base[j] < math.inf and to_base[j] < math.inf]
    return {
        "runs": [runs[j] for j in keep],
        "ski": [runs[j]["minutes"] for j in keep],
        "from_base": [from_base[j] for j in keep],
        "between": [[between[i][j] for j in keep] for i in keep],
        "to_base": [to_base[j] for j in keep],
        "base": base,
    }


def route_minutes(problem, order):
    """Total time of a day that skis the runs in a given order.

    Parameters
    ----------
    problem : dict
        From :func:`make_problem`.
    order : list of int
        Indexes of the runs, in the order they are skied.

    Returns
    -------
    float
        Minutes from leaving the base to coming back to it.
    """
    if not order:
        return 0.0
    total = problem["from_base"][order[0]]
    for previous, run in zip(order, order[1:]):
        total += problem["ski"][previous] + problem["between"][previous][run]
    return total + problem["ski"][order[-1]] + problem["to_base"][order[-1]]


def exact_route(problem, budget):
    """Best route, found with dynamic programming over subsets of runs.

    ``best[S][j]`` is the shortest time needed to ski exactly the set of
    runs ``S``, finishing at the bottom of run ``j``. Sets are handled by
    increasing size, so every value is final before it is used. The time
    is O(2^n * n^2) and the memory O(2^n * n), so this only works for about
    20 runs.

    Parameters
    ----------
    problem : dict
        From :func:`make_problem`.
    budget : float
        Time available, in minutes.

    Returns
    -------
    list of int
        Indexes of the runs, in the order they are skied. Among the routes
        with the most runs, the fastest one.
    """
    n = len(problem["runs"])
    ski = np.array(problem["ski"])
    between = np.array(problem["between"])
    to_base = np.array(problem["to_base"])

    masks = np.arange(1 << n)
    size = np.zeros(1 << n, dtype=np.int64)
    for bit in range(n):
        size += (masks >> bit) & 1

    best = np.full((1 << n, n), np.inf)
    parent = np.full((1 << n, n), -1, dtype=np.int8)
    for j in range(n):
        best[1 << j, j] = problem["from_base"][j] + ski[j]

    for k in range(1, n):
        layer = masks[size == k]
        for j in range(n):
            sets = layer[(layer >> j) & 1 == 0]
            # Coming from run i (in the set) to run j.
            options = best[sets] + between[:, j]
            came_from = options.argmin(axis=1)
            new_time = options[np.arange(len(sets)), came_from] + ski[j]
            new_time[new_time > budget] = np.inf
            targets = sets | (1 << j)
            better = new_time < best[targets, j]
            best[targets[better], j] = new_time[better]
            parent[targets[better], j] = came_from[better]

    total = best + to_base
    last = total.argmin(axis=1)
    day = total[masks, last]
    feasible = day <= budget
    if not feasible.any():
        return []
    most_runs = size[feasible].max()
    candidates = masks[feasible & (size == most_runs)]
    mask = int(candidates[day[candidates].argmin()])

    order, run = [], int(last[mask])
    while run != -1:
        order.append(run)
        previous = int(parent[mask, run])
        mask ^= 1 << run
        run = previous
    return order[::-1]


def brute_force_route(problem, budget):
    """Best route, found by trying every order of every set of runs.

    Only usable for very small problems (up to about 7 runs). It is used to
    check :func:`exact_route` in the tests.

    Parameters
    ----------
    problem : dict
        From :func:`make_problem`.
    budget : float
        Time available, in minutes.

    Returns
    -------
    list of int
        Indexes of the runs, in order. Among the routes with the most runs,
        the fastest one.
    """
    n = len(problem["runs"])
    for count in range(n, 0, -1):
        best, best_minutes = None, math.inf
        for order in itertools.permutations(range(n), count):
            minutes = route_minutes(problem, list(order))
            if minutes <= budget and minutes < best_minutes:
                best, best_minutes = list(order), minutes
        if best is not None:
            return best
    return []


def greedy_route(problem, budget):
    """Route built by always going to the nearest run not skied yet.

    A run is only chosen if there is still time to ski it and come back to
    the base afterwards.

    Parameters
    ----------
    problem : dict
        From :func:`make_problem`.
    budget : float
        Time available, in minutes.

    Returns
    -------
    list of int
        Indexes of the runs, in the order they are skied.
    """
    order, elapsed, current = [], 0.0, None
    remaining = set(range(len(problem["runs"])))
    while True:
        choice, choice_travel = None, math.inf
        for run in remaining:
            if current is None:
                travel = problem["from_base"][run]
            else:
                travel = problem["between"][current][run]
            end = elapsed + travel + problem["ski"][run] + problem["to_base"][run]
            if end <= budget and travel < choice_travel:
                choice, choice_travel = run, travel
        if choice is None:
            return order
        elapsed += choice_travel + problem["ski"][choice]
        order.append(choice)
        remaining.remove(choice)
        current = choice


def route_edges(graph, problem, order):
    """Every edge of a route, to print it or draw it on the map.

    Parameters
    ----------
    graph : ski_graph.SkiGraph
        The graph of the ski area.
    problem : dict
        From :func:`make_problem`.
    order : list of int
        Indexes of the runs, in the order they are skied.

    Returns
    -------
    list of dict
        Edges of the whole day, from the base back to the base.
    """
    edges, node = [], problem["base"]
    for index in order:
        run = problem["runs"][index]
        edges += ski_graph.fastest_path(graph, node, run["start"])
        edges += [graph.edges[i] for i in run["path"]]
        node = run["end"]
    return edges + ski_graph.fastest_path(graph, node, problem["base"])


if __name__ == "__main__":
    graph = ski_graph.build_graph(ski_data.get_runs(skip_beginner=False),
                                  ski_data.get_lifts())
    problem = make_problem(graph, graph.lift_bottom(BASE_LIFT))
    print(f"{len(problem['runs'])} runs:",
          ", ".join(run["name"] for run in problem["runs"]))

    print("\nBudget   Exact (runs, time)   Greedy (runs)")
    for hours in (1, 2, 3, 4):
        budget = hours * 60
        start = time.perf_counter()
        exact = exact_route(problem, budget)
        seconds = time.perf_counter() - start
        greedy = greedy_route(problem, budget)
        print(f"  {hours} h     {len(exact):2d} runs in {seconds:5.1f} s"
              f"        {len(greedy):2d} runs")

    order = exact_route(problem, 120)
    print("\nBest route in 2 hours:")
    ski_graph.print_path(route_edges(graph, problem, order))