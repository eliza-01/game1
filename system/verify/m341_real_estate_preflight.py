"""M341: non-destructive Real Estate / collision migration preflight.

Reads the active SQLite authoring registry and exported placement manifest.
Does not modify DB, manifests, Roblox Studio, published IDs, or Kanban.
Run from game1 root: python system/verify/m341_real_estate_preflight.py
Optional: --output artifacts/reports/m341_preflight.json
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sqlite3

COLLIDER = re.compile(r"(?:^|_)col(?:_|$)", re.IGNORECASE)
PLOTS = 50


def _json_object(raw: str | None) -> dict:
    value = json.loads(raw or "{}")
    if not isinstance(value, dict):
        raise ValueError("expected object in Real Estate registry")
    return value


def _registry_rows(db_file: Path) -> list[dict]:
    if not db_file.is_file():
        raise FileNotFoundError(f"Real Estate SQLite database is missing: {db_file}")
    # URI mode=ro: no CREATE/ALTER/INSERT. Do not use the Store constructor:
    # it runs schema migrations and exports on initialization.
    uri = db_file.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(
            "SELECT slug,skeleton_json,mesh_options_json,model_rigs_json "
            "FROM real_estate ORDER BY slug")]
    finally:
        connection.close()


def _read_placements(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f"Exported placement manifest is missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ValueError("Invalid Real Estate placement manifest")
    return data["items"]


def inspect(root: Path) -> dict:
    root = root.resolve()
    rows = _registry_rows(root / ".control-center" / "game1_real_estate.db")
    placements = _read_placements(root / "assets" / "manifests" / "real-estate-placements.json")
    by_house = Counter(str(p.get("houseSlug", "")) for p in placements)
    plots = {p.get("plotIndex") for p in placements
             if type(p.get("plotIndex")) is int and 1 <= p["plotIndex"] <= PLOTS}
    missing_house_anchor = sum(p.get("houseAnchorLocalCFrame") is None for p in placements)
    suspicious_placement = sum(type(p.get("plotIndex")) is not int
                               or not 1 <= p.get("plotIndex", 0) <= PLOTS for p in placements)
    houses = []
    warnings = []
    for row in rows:
        slug = row["slug"]
        skeleton = _json_object(row["skeleton_json"])
        meshes = skeleton.get("meshes", [])
        if not isinstance(meshes, list):
            raise ValueError(f"Invalid skeleton mesh list for {slug}")
        options = _json_object(row["mesh_options_json"])
        rigs = _json_object(row["model_rigs_json"])
        colliders = []
        collidable_non_collision = []
        geometry_vertices = 0
        for mesh in meshes:
            name = str(mesh.get("name", ""))
            verts = int(mesh.get("vertices", 0) or 0)
            geometry_vertices += verts
            settings = options.get(name) or {}
            if not isinstance(settings, dict):
                settings = {}
            is_col = bool(COLLIDER.search(name))
            entry = {"name": name, "vertices": verts,
                     "publishedRig": name in rigs,
                     "noCollide": settings.get("noCollide"),
                     "collisionFidelity": settings.get("collisionFidelity")}
            if is_col:
                colliders.append(entry)
            elif settings.get("noCollide") is False:
                collidable_non_collision.append(entry)
        if not colliders:
            warnings.append(f"{slug}: no legacy COL mesh in registered source")
        houses.append({"slug": slug, "placementBindings": by_house.get(slug, 0),
                       "meshCount": len(meshes), "totalSourceVertices": geometry_vertices,
                       "legacyColliders": colliders,
                       "otherCollidableMeshes": collidable_non_collision})
    unknown_placements = sorted(set(by_house) - {h["slug"] for h in houses})
    if unknown_placements:
        warnings.append("Placement manifest contains unregistered houses: " + ", ".join(unknown_placements))
    if suspicious_placement:
        warnings.append(f"{suspicious_placement} placement records have invalid plot indexes")
    return {
        "schemaVersion": 1,
        "kind": "m341_real_estate_read_only_preflight",
        "registeredHouses": len(houses),
        "placementBindings": len(placements),
        "distinctPlotsWithBindings": len(plots),
        "totalPlots": PLOTS,
        "placementsWithoutHouseAnchor": missing_house_anchor,
        "houses": houses,
        "warnings": warnings,
        "collisionMigrationEnabled": False,
        "note": "Read-only authoring snapshot; it does not inspect live Workspace, Studio physics or device FPS."
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, help="Optional report path; does not alter authoring data")
    args = parser.parse_args()
    report = inspect(args.project_root)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        path = args.output
        if not path.is_absolute():
            path = args.project_root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded, encoding="utf-8")
        print(f"M341 preflight written: {path}")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
