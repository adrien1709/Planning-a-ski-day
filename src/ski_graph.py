"""
ski_graph.py
====================================
Builds the directed graph of a ski area: runs go
downhill, lifts go uphill, and each edge is weighted by
its duration in minutes. Merges endpoints that are close
together and computes shortest travel times with Dijkstra.

| Author: Adrien Diaz
| Date: 2026 November 23
"""

import heapq
import math

import ski_data

#: Average skiing speed in km/h for each OpenSkiMap difficulty.
#: In Europe, novice = green, easy = blue, intermediate = red,
#: advanced and expert = black.
RUN_SPEED_KMH = {
    "novice": 20,
    "easy": 20,
    "intermediate": 25,
    "advanced": 30,
    "expert": 30,
    "freeride": 25,
}

#: Speed used when a run has no difficulty, in km/h.
DEFAULT_RUN_SPEED_KMH = 20

#: Lift speed in m/s for each OpenSkiMap lift type.
LIFT_SPEED_MS = {
    "chair_lift": 2.5,
    "drag_lift": 2.5,
    "t-bar": 2.5,
    "j-bar": 2.5,
    "platter": 2.5,
    "rope_tow": 2.5,
    "magic_carpet": 0.5,
}

#: Speed used for any other lift type (gondola, cable car...), in m/s.
DEFAULT_LIFT_SPEED_MS = 2.5

#: Waiting time at the bottom of each lift, in minutes.
LIFT_WAIT_MINUTES = 3

#: Two points closer than this are treated as the same place, in meters.
MERGE_DISTANCE_M = 40

#: Shortest run kept as a target, in meters. Shorter ones are small bits of
#: runs that are almost entirely on the other side of the Col du Tourmalet.
MIN_RUN_LENGTH_M = 100

#: Longest link added across a flat area where the data has a gap, in meters.
LINK_DISTANCE_M = 250

#: Speed on those links (pushing or skating on flat snow), in km/h.
LINK_SPEED_KMH = 5

EARTH_RADIUS_M = 6_371_000


def distance_m(point_a, point_b):
    """Distance between two points on the Earth (haversine formula).

    Parameters
    ----------
    point_a, point_b : tuple of float
        Points as ``(longitude, latitude)`` in degrees.

    Returns
    -------
    float
        Distance in meters.
    """
    lon1, lat1 = map(math.radians, point_a)
    lon2, lat2 = map(math.radians, point_b)
    a = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def line_length_m(coordinates):
    """Length of a line made of several points.

    Parameters
    ----------
    coordinates : list of tuple of float
        Points of the line as ``(longitude, latitude)``.

    Returns
    -------
    float
        Length in meters.
    """
    return sum(distance_m(a, b) for a, b in zip(coordinates, coordinates[1:]))


def run_minutes(length_m, difficulty):
    """Time needed to ski a run.

    Parameters
    ----------
    length_m : float
        Length of the run in meters.
    difficulty : str or None
        OpenSkiMap difficulty of the run.

    Returns
    -------
    float
        Duration in minutes.
    """
    speed_kmh = RUN_SPEED_KMH.get(difficulty, DEFAULT_RUN_SPEED_KMH)
    return length_m / (speed_kmh * 1000 / 60)


def lift_minutes(length_m, lift_type):
    """Time needed to wait for and ride a lift.

    Parameters
    ----------
    length_m : float
        Length of the lift in meters.
    lift_type : str or None
        OpenSkiMap type of the lift.

    Returns
    -------
    float
        Duration in minutes, waiting time included.
    """
    speed_ms = LIFT_SPEED_MS.get(lift_type, DEFAULT_LIFT_SPEED_MS)
    return LIFT_WAIT_MINUTES + length_m / speed_ms / 60


def split_runs_at_junctions(runs, lifts):
    """Cut runs where another run or a lift starts or ends in their middle.

    A run often joins another one halfway down, and lifts often start next
    to the middle of a run. To be able to switch there, the run is cut into
    pieces at that point.

    Parameters
    ----------
    runs : list of dict
        Runs from :func:`ski_data.get_runs`.
    lifts : list of dict
        Lifts from :func:`ski_data.get_lifts`.

    Returns
    -------
    list of dict
        The run pieces, with the same keys as the runs.
    """
    endpoints = []
    for item in runs + lifts:
        endpoints.append(item["coordinates"][0])
        endpoints.append(item["coordinates"][-1])

    pieces = []
    for run in runs:
        points = list(run["coordinates"])
        # Cut positions as (segment index, fraction along the segment).
        cuts = set()
        for endpoint in endpoints:
            best = None
            for i in range(len(points) - 1):
                t, d = closest_on_segment(endpoint, points[i], points[i + 1])
                if best is None or d < best[2]:
                    best = (i, t, d)
            i, t, d = best
            if d > MERGE_DISTANCE_M:
                continue
            # Too close to the ends of the run: no need to cut.
            cut_point = interpolate(points[i], points[i + 1], t)
            if min(distance_m(cut_point, points[0]),
                   distance_m(cut_point, points[-1])) <= MERGE_DISTANCE_M:
                continue
            cuts.add((i, round(t, 6)))

        current = [points[0]]
        for i in range(len(points) - 1):
            for _, t in sorted(c for c in cuts if c[0] == i):
                cut_point = interpolate(points[i], points[i + 1], t)
                current.append(cut_point)
                pieces.append({**run, "coordinates": current})
                current = [cut_point]
            current.append(points[i + 1])
        pieces.append({**run, "coordinates": current})
    return pieces


def to_meters(point, origin):
    """Local flat coordinates of a point, in meters, around an origin.

    Parameters
    ----------
    point, origin : tuple of float
        Points as ``(longitude, latitude)`` in degrees.

    Returns
    -------
    tuple of float
        ``(x, y)`` in meters east and north of ``origin``.
    """
    x = math.radians(point[0] - origin[0]) * math.cos(math.radians(origin[1]))
    y = math.radians(point[1] - origin[1])
    return x * EARTH_RADIUS_M, y * EARTH_RADIUS_M


def closest_on_segment(point, a, b):
    """Closest point of a segment to a given point.

    Parameters
    ----------
    point, a, b : tuple of float
        The point and the two ends of the segment, as
        ``(longitude, latitude)``.

    Returns
    -------
    t : float
        Position of the closest point along the segment, from 0 (at ``a``)
        to 1 (at ``b``).
    distance : float
        Distance from ``point`` to the segment, in meters.
    """
    px, py = to_meters(point, a)
    bx, by = to_meters(b, a)
    length2 = bx * bx + by * by
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, (px * bx + py * by) / length2))
    return t, math.hypot(px - t * bx, py - t * by)


def interpolate(a, b, t):
    """Point at a fraction of the way from ``a`` to ``b``.

    Parameters
    ----------
    a, b : tuple of float
        Points as ``(longitude, latitude)``.
    t : float
        Fraction, from 0 to 1.

    Returns
    -------
    tuple of float
        The point as ``(longitude, latitude)``.
    """
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


class SkiGraph:
    """Directed graph of a ski area.

    Nodes are places where you can switch between runs and lifts. Each edge
    is a run piece (going down) or a lift (going up).

    Attributes
    ----------
    positions : dict
        Node id -> ``(longitude, latitude)``.
    edges : list of dict
        Every edge, with the keys ``start``, ``end``, ``kind`` (``"run"`` or
        ``"lift"``), ``name``, ``difficulty`` or ``type``, ``length_m``,
        ``minutes`` and ``coordinates``.
    adjacency : dict
        Node id -> list of indexes in :attr:`edges` of the edges leaving it.
    """

    def __init__(self):
        self.positions = {}
        self.edges = []
        self.adjacency = {}

    def node_at(self, point):
        """Node at a given place, created if there is none close enough.

        Parameters
        ----------
        point : tuple of float
            ``(longitude, latitude)`` of the place.

        Returns
        -------
        int
            Id of the node.
        """
        for node, position in self.positions.items():
            if distance_m(position, point) <= MERGE_DISTANCE_M:
                return node
        node = len(self.positions)
        self.positions[node] = point
        self.adjacency[node] = []
        return node

    def add_edge(self, item, kind):
        """Add a run piece or a lift to the graph.

        Parameters
        ----------
        item : dict
            Run piece or lift, with at least ``name`` and ``coordinates``.
        kind : str
            ``"run"`` or ``"lift"``.
        """
        coordinates = item["coordinates"]
        length = line_length_m(coordinates)
        if kind == "run":
            minutes = run_minutes(length, item["difficulty"])
        else:
            minutes = lift_minutes(length, item["type"])
        edge = dict(item)
        edge.update({
            "start": self.node_at(coordinates[0]),
            "end": self.node_at(coordinates[-1]),
            "kind": kind,
            "length_m": length,
            "minutes": minutes,
        })
        self.adjacency[edge["start"]].append(len(self.edges))
        self.edges.append(edge)

    def lift_bottom(self, name):
        """Node at the bottom of a lift.

        Parameters
        ----------
        name : str
            Name of the lift.

        Returns
        -------
        int
            Id of the node.
        """
        return self._lift(name)["start"]

    def lift_top(self, name):
        """Node at the top of a lift.

        Parameters
        ----------
        name : str
            Name of the lift.

        Returns
        -------
        int
            Id of the node.
        """
        return self._lift(name)["end"]

    def _lift(self, name):
        for edge in self.edges:
            if edge["kind"] == "lift" and edge["name"] == name:
                return edge
        raise KeyError(f"No lift named {name!r}")


def build_graph(runs, lifts):
    """Build the graph of a ski area.

    Parameters
    ----------
    runs : list of dict
        Runs from :func:`ski_data.get_runs`.
    lifts : list of dict
        Lifts from :func:`ski_data.get_lifts`.

    Returns
    -------
    SkiGraph
        The graph, with every run piece and every lift as an edge.
    """
    graph = SkiGraph()
    for lift in lifts:
        graph.add_edge(lift, "lift")
    for piece in split_runs_at_junctions(runs, lifts):
        graph.add_edge(piece, "run")
    add_links(graph)
    return graph


def add_links(graph, max_distance_m=LINK_DISTANCE_M):
    """Add short links across flat areas where the data has gaps.

    At the bottom of the ski area, runs often end on a flat snow area and
    the lifts start a few hundred meters away. Skiers cross it, but the
    data has no line there. Each dead end (a node you cannot leave) is
    linked to the nearby nodes you can leave, and each node you cannot
    reach (such as a lift bottom) is linked from the nearby nodes you can
    reach. The bottom of each run is also linked to every lift that starts
    nearby. Links are crossed at :data:`LINK_SPEED_KMH`.

    Parameters
    ----------
    graph : SkiGraph
        The graph, changed in place.
    max_distance_m : float, optional
        Longest link allowed, in meters.
    """
    has_exit = {node for node in graph.positions if graph.adjacency[node]}
    has_entry = {edge["end"] for edge in graph.edges}
    run_ends = {edge["end"] for edge in graph.edges if edge["kind"] == "run"}
    lift_bottoms = {edge["start"] for edge in graph.edges if edge["kind"] == "lift"}
    new_links = set()
    # From the bottom of a run, you can reach any lift that starts nearby.
    for end in run_ends:
        for bottom in lift_bottoms:
            if distance_m(graph.positions[end], graph.positions[bottom]) <= max_distance_m:
                new_links.add((end, bottom))
    for node, position in graph.positions.items():
        if node not in has_exit:
            for other in has_exit:
                if distance_m(position, graph.positions[other]) <= max_distance_m:
                    new_links.add((node, other))
        if node not in has_entry:
            for other in has_entry:
                if distance_m(position, graph.positions[other]) <= max_distance_m:
                    new_links.add((other, node))

    for start, end in sorted(new_links):
        if start == end:
            continue
        length = distance_m(graph.positions[start], graph.positions[end])
        graph.adjacency[start].append(len(graph.edges))
        graph.edges.append({
            "start": start,
            "end": end,
            "kind": "link",
            "name": None,
            "length_m": length,
            "minutes": length / (LINK_SPEED_KMH * 1000 / 60),
            "coordinates": [graph.positions[start], graph.positions[end]],
        })


def strongly_connected_components(graph):
    """Groups of nodes where each node can reach every other one.

    Uses Kosaraju's algorithm: a first depth-first search gives an order of
    the nodes, and a second one on the reversed graph collects the groups.

    Parameters
    ----------
    graph : SkiGraph
        The graph.

    Returns
    -------
    list of set
        The components, largest first.
    """
    reverse = {node: [] for node in graph.positions}
    for edge in graph.edges:
        reverse[edge["end"]].append(edge["start"])

    # First pass: nodes in the order their search finishes.
    order, visited = [], set()
    for root in graph.positions:
        if root in visited:
            continue
        visited.add(root)
        stack = [(root, iter(graph.adjacency[root]))]
        while stack:
            node, children = stack[-1]
            for index in children:
                child = graph.edges[index]["end"]
                if child not in visited:
                    visited.add(child)
                    stack.append((child, iter(graph.adjacency[child])))
                    break
            else:
                stack.pop()
                order.append(node)

    # Second pass on the reversed graph, latest finished node first.
    components, assigned = [], set()
    for root in reversed(order):
        if root in assigned:
            continue
        component, stack = set(), [root]
        assigned.add(root)
        while stack:
            node = stack.pop()
            component.add(node)
            for parent in reverse[node]:
                if parent not in assigned:
                    assigned.add(parent)
                    stack.append(parent)
        components.append(component)
    return sorted(components, key=len, reverse=True)


def dijkstra(graph, source):
    """Fastest time from one node to every other node.

    Parameters
    ----------
    graph : SkiGraph
        The graph.
    source : int
        Starting node.

    Returns
    -------
    minutes : dict
        Node id -> shortest time in minutes from ``source``. Nodes that
        cannot be reached are missing.
    previous_edge : dict
        Node id -> index of the last edge on the fastest path to it.
    """
    minutes = {source: 0.0}
    previous_edge = {}
    queue = [(0.0, source)]
    done = set()
    while queue:
        time, node = heapq.heappop(queue)
        if node in done:
            continue
        done.add(node)
        for index in graph.adjacency[node]:
            edge = graph.edges[index]
            new_time = time + edge["minutes"]
            if new_time < minutes.get(edge["end"], math.inf):
                minutes[edge["end"]] = new_time
                previous_edge[edge["end"]] = index
                heapq.heappush(queue, (new_time, edge["end"]))
    return minutes, previous_edge


def fastest_path(graph, source, target):
    """Fastest path between two nodes.

    Parameters
    ----------
    graph : SkiGraph
        The graph.
    source, target : int
        Starting and ending nodes.

    Returns
    -------
    list of dict
        The edges of the path, in order. Empty if ``target`` cannot be
        reached.
    """
    _, previous_edge = dijkstra(graph, source)
    if target != source and target not in previous_edge:
        return []
    path, node = [], target
    while node != source:
        edge = graph.edges[previous_edge[node]]
        path.append(edge)
        node = edge["start"]
    return path[::-1]


def target_runs(graph):
    """The runs to ski, each one as a single block from its top to its bottom.

    A named run is often made of several pieces in the graph, and can split
    into two branches. Skiing a run means skiing its longest line from top
    to bottom in one go, using only pieces that carry its name. Beginner
    runs are not targets, and neither are runs shorter than
    :data:`MIN_RUN_LENGTH_M`.

    Parameters
    ----------
    graph : SkiGraph
        The graph.

    Returns
    -------
    list of dict
        One dict per run, sorted by name, with the keys ``name``, ``start``
        (top node), ``end`` (bottom node), ``minutes``, ``length_m`` and
        ``path`` (list of edge indexes, in order).
    """
    pieces_by_name = {}
    for index, edge in enumerate(graph.edges):
        if edge["kind"] != "run" or not edge["name"]:
            continue
        if edge["difficulty"] == "novice":
            continue
        for name in edge["name"].split(","):
            pieces_by_name.setdefault(name.strip(), []).append(index)

    runs = []
    for name, pieces in sorted(pieces_by_name.items()):
        best = longest_line(graph, pieces)
        length = sum(graph.edges[i]["length_m"] for i in best)
        if length < MIN_RUN_LENGTH_M:
            continue
        runs.append({
            "name": name,
            "start": graph.edges[best[0]]["start"],
            "end": graph.edges[best[-1]]["end"],
            "minutes": sum(graph.edges[i]["minutes"] for i in best),
            "length_m": length,
            "path": best,
        })
    return runs


def longest_line(graph, pieces):
    """Longest chain of pieces that can be skied one after the other.

    Tries every chain that never comes back to a node it already passed
    through. A run has at most a few pieces, so this is fast.

    Parameters
    ----------
    graph : SkiGraph
        The graph.
    pieces : list of int
        Indexes of the edges that make up the run.

    Returns
    -------
    list of int
        Edge indexes of the longest chain, in order.
    """
    leaving = {}
    for index in pieces:
        leaving.setdefault(graph.edges[index]["start"], []).append(index)

    best, best_length = [], -1.0

    def extend(chain, visited, length):
        nonlocal best, best_length
        if length > best_length:
            best, best_length = list(chain), length
        node = graph.edges[chain[-1]]["end"]
        for index in leaving.get(node, []):
            nxt = graph.edges[index]["end"]
            if nxt not in visited:
                chain.append(index)
                visited.add(nxt)
                extend(chain, visited, length + graph.edges[index]["length_m"])
                visited.remove(nxt)
                chain.pop()

    for first in pieces:
        edge = graph.edges[first]
        extend([first], {edge["start"], edge["end"]}, edge["length_m"])
    return best


def travel_times(graph, runs, base):
    """Fastest travel times between the runs, and to and from the base.

    Parameters
    ----------
    graph : SkiGraph
        The graph.
    runs : list of dict
        Runs from :func:`target_runs`.
    base : int
        Node where the day starts and ends.

    Returns
    -------
    from_base : list of float
        ``from_base[j]``: minutes from the base to the top of run ``j``.
    between : list of list of float
        ``between[i][j]``: minutes from the bottom of run ``i`` to the top
        of run ``j``.
    to_base : list of float
        ``to_base[i]``: minutes from the bottom of run ``i`` back to the base.

    Times are ``math.inf`` when there is no way to go.
    """
    from_start, _ = dijkstra(graph, base)
    from_base = [from_start.get(run["start"], math.inf) for run in runs]
    between, to_base = [], []
    for run in runs:
        minutes, _ = dijkstra(graph, run["end"])
        between.append([minutes.get(other["start"], math.inf) for other in runs])
        to_base.append(minutes.get(base, math.inf))
    return from_base, between, to_base


def print_path(path, start_time="09:00"):
    """Print a path as an itinerary with start times.

    Parameters
    ----------
    path : list of dict
        Edges returned by :func:`fastest_path`.
    start_time : str, optional
        Time of the first edge, as ``"HH:MM"``.
    """
    hours, mins = map(int, start_time.split(":"))
    clock = hours * 60 + mins
    for edge in path:
        if edge["kind"] == "run":
            label = edge["difficulty"] or ""
        elif edge["kind"] == "lift":
            label = edge["type"] or ""
        else:
            label = "flat link"
        print(f"  {int(clock) // 60:02d}:{int(clock) % 60:02d}  {edge['kind']:<4}  "
              f"{edge['name'] or '(no name)':<22} {label:<13} "
              f"{edge['minutes']:5.1f} min")
        clock += edge["minutes"]
    total = sum(edge["minutes"] for edge in path)
    print(f"  Total: {total:.1f} min")


if __name__ == "__main__":
    # Beginner runs stay in the graph: some of them are the only way
    # between two parts of the ski area.
    graph = build_graph(ski_data.get_runs(skip_beginner=False),
                        ski_data.get_lifts())
    counts = {kind: sum(edge["kind"] == kind for edge in graph.edges)
              for kind in ("run", "lift", "link")}
    print(f"La Mongie graph: {len(graph.positions)} nodes, "
          f"{counts['run']} run pieces, {counts['lift']} lifts, "
          f"{counts['link']} flat links")

    components = strongly_connected_components(graph)
    main = components[0]
    print(f"Largest strongly connected part: {len(main)} of "
          f"{len(graph.positions)} nodes")
    outside = sorted({edge["name"] for edge in graph.edges
                      if edge["name"] and not (edge["start"] in main
                                               and edge["end"] in main)})
    if outside:
        print("Runs and lifts not fully in it:", ", ".join(outside))

    source, target = graph.lift_bottom("Sud"), graph.lift_top("Pourteilh")
    print("\nFastest way from the bottom of Sud to the top of Pourteilh:")
    print_path(fastest_path(graph, source, target))