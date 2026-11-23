"""Tests for ski_graph.py. Run them from the project folder with ``pytest``."""

import random
import sys
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import ski_graph  # noqa: E402


def make_graph(n_nodes, edges):
    """Small hand-made graph. ``edges`` is a list of (start, end, minutes)."""
    graph = ski_graph.SkiGraph()
    for node in range(n_nodes):
        graph.positions[node] = (0.0, float(node))
        graph.adjacency[node] = []
    for start, end, minutes in edges:
        graph.adjacency[start].append(len(graph.edges))
        graph.edges.append({"start": start, "end": end, "minutes": minutes,
                            "kind": "run", "name": f"{start}-{end}"})
    return graph


def test_dijkstra_small_example():
    # 0 -> 1 -> 3 takes 3 minutes, 0 -> 2 -> 3 takes 6 minutes.
    graph = make_graph(4, [(0, 1, 1), (1, 3, 2), (0, 2, 1), (2, 3, 5)])
    minutes, _ = ski_graph.dijkstra(graph, 0)
    assert minutes[3] == 3
    path = ski_graph.fastest_path(graph, 0, 3)
    assert [edge["name"] for edge in path] == ["0-1", "1-3"]


def test_unreachable_node():
    graph = make_graph(3, [(0, 1, 1)])
    assert ski_graph.fastest_path(graph, 0, 2) == []


def test_dijkstra_matches_networkx():
    rng = random.Random(0)
    for _ in range(20):
        n = 15
        edges = [(rng.randrange(n), rng.randrange(n), rng.uniform(1, 10))
                 for _ in range(40)]
        graph = make_graph(n, edges)
        reference = nx.MultiDiGraph()
        reference.add_nodes_from(range(n))
        for start, end, minutes in edges:
            reference.add_edge(start, end, weight=minutes)
        for source in range(n):
            mine, _ = ski_graph.dijkstra(graph, source)
            expected = nx.single_source_dijkstra_path_length(reference, source)
            assert mine.keys() == expected.keys()
            for node in expected:
                assert abs(mine[node] - expected[node]) < 1e-9


def test_strongly_connected_components():
    # 0, 1, 2 form a loop; 3 can be reached but you cannot come back.
    graph = make_graph(4, [(0, 1, 1), (1, 2, 1), (2, 0, 1), (2, 3, 1)])
    components = ski_graph.strongly_connected_components(graph)
    assert components[0] == {0, 1, 2}
    assert {3} in components