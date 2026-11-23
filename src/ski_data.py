"""
ski_data.py
====================================
Downloads and reads the OpenSkiMap data. Keeps the
downhill runs and the lifts in service for a given ski
area, such as La Mongie or the Grand Tourmalet.

| Author: Adrien Diaz
| Date: 2026 November 23
"""

import json
import time
from pathlib import Path

import requests

#: Folder where the data files are saved (ignored by git).
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

#: Address of the OpenSkiMap GeoJSON files.
OPENSKIMAP_URL = "https://tiles.openskimap.org/geojson/{name}.geojson"

#: Name of the ski area in the OpenSkiMap data.
GRAND_TOURMALET = "Grand Tourmalet"

#: Longitude of the Col du Tourmalet. La Mongie is east of it, Barèges west.
COL_DU_TOURMALET_LONGITUDE = 0.1453

#: Lifts that are not part of the ski area (tourist cable cars).
EXCLUDED_LIFTS = ("Pic du Midi",)


def download_geojson(name, max_attempts=3, wait_seconds=30):
    """Download an OpenSkiMap GeoJSON file, unless it is already saved.

    The OpenSkiMap server is sometimes slow, so a failed download is
    tried again a few times before giving up.

    Parameters
    ----------
    name : str
        Name of the file to download: ``"runs"``, ``"lifts"`` or ``"ski_areas"``.
    max_attempts : int, optional
        Number of tries before giving up.
    wait_seconds : int, optional
        Time to wait between two tries, in seconds.

    Returns
    -------
    pathlib.Path
        Path of the saved file.
    """
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / f"{name}.geojson"
    if path.exists():
        return path

    url = OPENSKIMAP_URL.format(name=name)
    # The file is written under a temporary name and renamed at the end,
    # so an interrupted download never leaves an incomplete file behind.
    partial_path = DATA_DIR / f"{name}.geojson.part"
    for attempt in range(1, max_attempts + 1):
        print(f"Downloading {url} (attempt {attempt}/{max_attempts}) ...")
        try:
            with requests.get(url, stream=True, timeout=(30, 600)) as response:
                response.raise_for_status()
                with open(partial_path, "wb") as file:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        file.write(chunk)
            partial_path.replace(path)
            return path
        except requests.exceptions.RequestException as error:
            print(f"Download failed: {error}")
            if attempt < max_attempts:
                print(f"Trying again in {wait_seconds} seconds ...")
                time.sleep(wait_seconds)
    raise RuntimeError(f"Could not download {url} after {max_attempts} attempts")


def extract_ski_area(name, ski_area_name=GRAND_TOURMALET):
    """Keep only the features of one ski area and save them in a small file.

    The world files are very large, so they are read only once. The next
    calls read the small file directly.

    Parameters
    ----------
    name : str
        ``"runs"`` or ``"lifts"``.
    ski_area_name : str, optional
        Name of the ski area in the OpenSkiMap data.

    Returns
    -------
    list of dict
        The GeoJSON features of this ski area.
    """
    slug = ski_area_name.lower().replace(" ", "_")
    small_path = DATA_DIR / f"{slug}_{name}.geojson"
    if small_path.exists():
        with open(small_path, encoding="utf-8") as file:
            return json.load(file)["features"]

    world_path = download_geojson(name)
    print(f"Reading {world_path.name} (this can take a minute) ...")
    with open(world_path, encoding="utf-8") as file:
        features = json.load(file)["features"]

    kept = [
        feature
        for feature in features
        if any(
            area["properties"]["name"] == ski_area_name
            for area in feature["properties"]["skiAreas"]
        )
    ]
    with open(small_path, "w", encoding="utf-8") as file:
        json.dump({"type": "FeatureCollection", "features": kept}, file)
    return kept


def mean_longitude(coordinates):
    """Average longitude of a line.

    Parameters
    ----------
    coordinates : list of list of float
        Points of the line as ``[longitude, latitude, ...]``.

    Returns
    -------
    float
        Average longitude in degrees.
    """
    return sum(point[0] for point in coordinates) / len(coordinates)


def is_in_la_mongie(coordinates):
    """Tell if a run or lift is on the La Mongie side of the Grand Tourmalet.

    Parameters
    ----------
    coordinates : list of list of float
        Points of the line as ``[longitude, latitude, ...]``.

    Returns
    -------
    bool
        ``True`` if the line is east of the Col du Tourmalet.
    """
    return mean_longitude(coordinates) > COL_DU_TOURMALET_LONGITUDE


def get_runs(la_mongie_only=True, skip_beginner=True):
    """Downhill runs of the Grand Tourmalet that are open.

    Parameters
    ----------
    la_mongie_only : bool, optional
        Keep only the runs on the La Mongie side.
    skip_beginner : bool, optional
        Remove the beginner runs (difficulty ``"novice"``).

    Returns
    -------
    list of dict
        One dict per run, with the keys ``id``, ``name``, ``difficulty``
        and ``coordinates`` (list of ``(longitude, latitude)``).
    """
    runs = []
    for feature in extract_ski_area("runs"):
        properties = feature["properties"]
        geometry = feature["geometry"]
        if geometry["type"] != "LineString":
            continue
        if "downhill" not in properties["uses"]:
            continue
        if properties["status"] != "operating":
            continue
        if skip_beginner and properties["difficulty"] == "novice":
            continue
        if la_mongie_only and not is_in_la_mongie(geometry["coordinates"]):
            continue
        runs.append({
            "id": properties["id"],
            "name": properties["name"],
            "difficulty": properties["difficulty"],
            "coordinates": [(p[0], p[1]) for p in geometry["coordinates"]],
        })
    return runs


def get_lifts(la_mongie_only=True):
    """Lifts of the Grand Tourmalet that are in service.

    Parameters
    ----------
    la_mongie_only : bool, optional
        Keep only the lifts on the La Mongie side.

    Returns
    -------
    list of dict
        One dict per lift, with the keys ``id``, ``name``, ``type``
        and ``coordinates`` (list of ``(longitude, latitude)``).
    """
    lifts = []
    for feature in extract_ski_area("lifts"):
        properties = feature["properties"]
        geometry = feature["geometry"]
        name = properties["name"] or ""
        if geometry["type"] != "LineString":
            continue
        if properties["status"] != "operating":
            continue
        if any(excluded in name for excluded in EXCLUDED_LIFTS):
            continue
        if la_mongie_only and not is_in_la_mongie(geometry["coordinates"]):
            continue
        lifts.append({
            "id": properties["id"],
            "name": properties["name"],
            "type": properties["liftType"],
            "coordinates": [(p[0], p[1]) for p in geometry["coordinates"]],
        })
    return lifts


if __name__ == "__main__":
    runs = get_runs()
    lifts = get_lifts()
    # A segment shared by several runs is named "Run A, Run B".
    names = sorted({name.strip() for run in runs if run["name"]
                    for name in run["name"].split(",")})
    print(f"La Mongie: {len(runs)} run segments, {len(names)} named runs, "
          f"{len(lifts)} lifts")
    print("Runs:", ", ".join(names))
    print("Lifts:", ", ".join(sorted(lift["name"] or "?" for lift in lifts)))