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
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

import ski_data
import ski_graph

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

    legend = [
        Line2D([], [], color=RUN_COLORS["novice"], label="Green run"),
        Line2D([], [], color=RUN_COLORS["easy"], label="Blue run"),
        Line2D([], [], color=RUN_COLORS["intermediate"], label="Red run"),
        Line2D([], [], color=RUN_COLORS["advanced"], label="Black run"),
        Line2D([], [], color=RUN_COLORS["freeride"], label="Freeride"),
        Line2D([], [], color=LIFT_COLOR, marker="o", markersize=3, label="Lift"),
    ]
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