"""
ski_plots.py
====================================
Draws the ski area and the routes on a map, and makes
the plots used in the README: runs skied vs. time budget,
running time of the exact method and comparison of
the heuristics.

| Author: Adrien Diaz
| Date: 2026 November 23
"""

import math
import time
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

import ski_data
import ski_graph
import ski_planner

#: Folder where the images are saved.
IMAGES_DIR = Path(__file__).resolve().parent.parent / "images"

#: Color of each run difficulty (European colors).
RUN_COLORS = {
    "novice": "#2e9e44",
    "easy": "#1f6fd1",
    "intermediate": "#d62728",
    "advanced": "#111111",
    "expert": "#111111",
    "freeride": "#ff8c00",
}

#: Color of a run with no difficulty.
DEFAULT_RUN_COLOR = "#888888"

LIFT_COLOR = "#6b3fa0"
LINK_COLOR = "#bbbbbb"
ROUTE_COLOR = "#ffd400"

#: Colors of the methods in the plots (first two slots of a colorblind-safe
#: palette).
EXACT_COLOR = "#2a78d6"
GREEDY_COLOR = "#eb6834"
INK = "#3d3d3a"
GRID = "#e4e3de"


def draw_edge(ax, edge, scale):
    """Draw one run, lift or flat link.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Where to draw.
    edge : dict
        Edge of a :class:`ski_graph.SkiGraph`.
    scale : float
        Factor applied to longitudes so that distances look right on the map.
    """
    xs = [point[0] * scale for point in edge["coordinates"]]
    ys = [point[1] for point in edge["coordinates"]]
    if edge["kind"] == "run":
        color = RUN_COLORS.get(edge["difficulty"], DEFAULT_RUN_COLOR)
        ax.plot(xs, ys, color=color, linewidth=1.8, zorder=2)
    elif edge["kind"] == "lift":
        ax.plot(xs, ys, color=LIFT_COLOR, linewidth=1.2, zorder=3)
        ax.plot([xs[0], xs[-1]], [ys[0], ys[-1]], "o", color=LIFT_COLOR,
                markersize=3, zorder=3)
    else:
        ax.plot(xs, ys, color=LINK_COLOR, linewidth=0.8, linestyle=":",
                zorder=1)


def plot_ski_area(graph, title, filename, route=None, show_links=False):
    """Draw a ski area, and a route on it if one is given.

    Parameters
    ----------
    graph : ski_graph.SkiGraph
        The graph of the ski area.
    title : str
        Title of the figure.
    filename : str
        Name of the image file, saved in :data:`IMAGES_DIR`.
    route : list of dict, optional
        Edges of a route to highlight, in order.
    show_links : bool, optional
        Also draw the flat links added where the data has gaps.

    Returns
    -------
    pathlib.Path
        Path of the saved image.
    """
    mean_latitude = sum(p[1] for p in graph.positions.values()) / len(graph.positions)
    scale = math.cos(math.radians(mean_latitude))

    fig, ax = plt.subplots(figsize=(10, 8))
    if route:
        for edge in route:
            xs = [point[0] * scale for point in edge["coordinates"]]
            ys = [point[1] for point in edge["coordinates"]]
            ax.plot(xs, ys, color=ROUTE_COLOR, linewidth=7, alpha=0.8,
                    solid_capstyle="round", zorder=1)
    for edge in graph.edges:
        if edge["kind"] != "link" or show_links:
            draw_edge(ax, edge, scale)

    # Only the difficulties that appear on the map go in the legend.
    present = {edge.get("difficulty") for edge in graph.edges
               if edge["kind"] == "run"}
    labels = [("novice", "Green run"), ("easy", "Blue run"),
              ("intermediate", "Red run"), ("advanced", "Black run"),
              ("freeride", "Freeride")]
    legend = [Line2D([], [], color=RUN_COLORS[level], label=label)
              for level, label in labels
              if level in present or (level == "advanced" and "expert" in present)]
    legend.append(Line2D([], [], color=LIFT_COLOR, marker="o", markersize=3,
                         label="Lift"))
    if route:
        legend.append(Line2D([], [], color=ROUTE_COLOR, linewidth=6, label="Route"))
    ax.legend(handles=legend, loc="best", fontsize=9)
    ax.set_title(title)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    fig.tight_layout()

    IMAGES_DIR.mkdir(exist_ok=True)
    path = IMAGES_DIR / filename
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def style_axes(ax):
    """Light grid and gray axes, so the data stands out.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The axes to style.
    """
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK)
    ax.tick_params(colors=INK)


def save(fig, filename):
    """Save a figure in :data:`IMAGES_DIR` and close it.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The figure.
    filename : str
        Name of the image file.

    Returns
    -------
    pathlib.Path
        Path of the saved image.
    """
    IMAGES_DIR.mkdir(exist_ok=True)
    path = IMAGES_DIR / filename
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_runs_vs_budget(problem, budgets, filename="runs_vs_budget.png"):
    """Number of runs skied by the exact and greedy methods for each budget.

    Parameters
    ----------
    problem : dict
        From :func:`ski_planner.make_problem`.
    budgets : list of int
        Time budgets to try, in minutes.
    filename : str, optional
        Name of the image file.

    Returns
    -------
    pathlib.Path
        Path of the saved image.
    """
    exact = [len(ski_planner.exact_route(problem, b)) for b in budgets]
    greedy = [len(ski_planner.greedy_route(problem, b)) for b in budgets]
    hours = [b / 60 for b in budgets]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(hours, exact, color=EXACT_COLOR, linewidth=2, marker="o",
            markersize=5, label="Exact (optimum)")
    ax.plot(hours, greedy, color=GREEDY_COLOR, linewidth=2, marker="s",
            markersize=5, label="Greedy")
    ax.axhline(len(problem["runs"]), color=INK, linewidth=0.8, linestyle="--")
    ax.text(hours[0], len(problem["runs"]) + 0.3,
            f"All {len(problem['runs'])} runs", color=INK, fontsize=9)
    ax.set_xlabel("Time budget (hours)", color=INK)
    ax.set_ylabel("Different runs skied", color=INK)
    ax.set_title("Runs skied at La Mongie vs. time budget", color=INK)
    ax.set_ylim(0, len(problem["runs"]) + 1.5)
    ax.legend(frameon=False, loc="lower right")
    style_axes(ax)
    return save(fig, filename)


def plot_exact_runtime(problem, budget, filename="exact_runtime.png"):
    """Running time of the exact method as the number of runs grows.

    The method is run on the first ``n`` runs of the problem, for every
    ``n`` from 6 to the total number of runs.

    Parameters
    ----------
    problem : dict
        From :func:`ski_planner.make_problem`.
    budget : float
        Time budget in minutes. A large budget keeps every state, which
        shows the real cost of the method.
    filename : str, optional
        Name of the image file.

    Returns
    -------
    pathlib.Path
        Path of the saved image.
    """
    sizes, seconds = [], []
    for n in range(6, len(problem["runs"]) + 1):
        keep = list(range(n))
        small = {
            "runs": problem["runs"][:n],
            "ski": problem["ski"][:n],
            "from_base": problem["from_base"][:n],
            "between": [[problem["between"][i][j] for j in keep] for i in keep],
            "to_base": problem["to_base"][:n],
            "base": problem["base"],
        }
        start = time.perf_counter()
        ski_planner.exact_route(small, budget)
        sizes.append(n)
        seconds.append(time.perf_counter() - start)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(sizes, seconds, color=EXACT_COLOR, linewidth=2, marker="o",
            markersize=5)
    ax.set_yscale("log")
    ax.set_xlabel("Number of runs", color=INK)
    ax.set_ylabel("Running time (seconds, log scale)", color=INK)
    ax.set_title("Running time of the exact method", color=INK)
    ax.text(sizes[-1], seconds[-1], f"  {seconds[-1]:.2f} s", color=INK,
            fontsize=9, va="center")
    style_axes(ax)
    return save(fig, filename)


if __name__ == "__main__":
    graph = ski_graph.build_graph(ski_data.get_runs(skip_beginner=False),
                                  ski_data.get_lifts())
    print("Saved", plot_ski_area(graph, "La Mongie: runs and lifts",
                                 "la_mongie_map.png"))

    route = ski_graph.fastest_path(graph, graph.lift_bottom("Sud"),
                                   graph.lift_top("Pourteilh"))
    print("Saved", plot_ski_area(
        graph, "Fastest way from the bottom of Sud to the top of Pourteilh",
        "dijkstra_example.png", route=route))

    problem = ski_planner.make_problem(
        graph, graph.lift_bottom(ski_planner.BASE_LIFT))
    order = ski_planner.exact_route(problem, 120)
    print("Saved", plot_ski_area(
        graph, f"Best route in 2 hours: {len(order)} runs",
        "route_la_mongie.png",
        route=ski_planner.route_edges(graph, problem, order)))
    print("Saved", plot_runs_vs_budget(problem, list(range(30, 361, 30))))
    print("Saved", plot_exact_runtime(problem, budget=600))