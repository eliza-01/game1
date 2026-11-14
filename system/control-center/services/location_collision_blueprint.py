"""Location Assets Collision Blueprint v1: validated Roblox Part recipes.

Authoring stores transforms RELATIVE to the registered Model:GetPivot().
This module never mutates Roblox Studio, places Parts, or accepts MeshParts.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time

SLUG = re.compile(r"[a-z0-9][a-z0-9_]{0,63}\Z")
PART_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]{0,63}\Z")
GROUP = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\- ]{0,63}\Z")
SHAPES = frozenset(("Block", "Ball", "Cylinder", "Wedge", "CornerWedge"))
MAX_PARTS = 256


def _finite(value, label: str, *, absolute: float = 100_000.0) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > absolute:
        raise ValueError(f"{label} must be a finite bounded number")
    return float(value)


def validate(value: dict, *, slug: str) -> dict:
    """Return canonical JSON-safe blueprint; reject unknown keys and partial captures.

    CFrame is 12 components from Roblox CFrame:GetComponents(): XYZ + 3x3
    orientation in row-major order. Rotation must be orthonormal with det +1.
    """
    if not SLUG.fullmatch(slug):
        raise ValueError("invalid Location Asset slug")
    if not isinstance(value, dict) or set(value) != {"schemaVersion", "pivot", "parts"}:
        raise ValueError("blueprint must contain schemaVersion, pivot, parts only")
    if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1:
        raise ValueError("unsupported collision blueprint schemaVersion")
    if value["pivot"] != "Model:GetPivot()":
        raise ValueError("collision blueprint pivot must use Model:GetPivot()")
    raw = value["parts"]
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_PARTS:
        raise ValueError("collision blueprint requires 1..256 Parts")
    parts = []
    ids = set()
    for index, part in enumerate(raw):
        label = f"parts[{index}]"
        if not isinstance(part, dict) or set(part) != {"id", "name", "shape", "size", "localCFrame", "collisionGroup", "canQuery", "canTouch"}:
            raise ValueError(f"{label}: invalid Part recipe fields")
        identifier = part["id"]
        name = part["name"]
        shape = part["shape"]
        if not isinstance(identifier, str) or not PART_ID.fullmatch(identifier) or identifier in ids:
            raise ValueError(f"{label}: duplicate or invalid Part ID")
        ids.add(identifier)
        if not isinstance(name, str) or not 1 <= len(name) <= 96 or any(ord(ch) < 32 for ch in name):
            raise ValueError(f"{label}: invalid name")
        if not isinstance(shape, str) or shape not in SHAPES:
            raise ValueError(f"{label}: shape must be a Roblox Part/WedgePart primitive")
        size = part["size"]
        if not isinstance(size, list) or len(size) != 3:
            raise ValueError(f"{label}: size must be a three-number array")
        size = [_finite(x, f"{label}.size", absolute=4096.0) for x in size]
        if any(x <= 0.001 for x in size):
            raise ValueError(f"{label}: size must be positive")
        frame = part["localCFrame"]
        if not isinstance(frame, list) or len(frame) != 12:
            raise ValueError(f"{label}: localCFrame requires 12 numbers")
        frame = [_finite(v, f"{label}.localCFrame") for v in frame]
        x, y, z = (frame[3:6], frame[6:9], frame[9:12])
        dot = lambda a,b: sum(p*q for p,q in zip(a,b))
        if any(abs(dot(v,v)-1.0) > 0.002 for v in (x,y,z)) or any(
            abs(dot(a,b)) > 0.002 for a,b in ((x,y),(x,z),(y,z))):
            raise ValueError(f"{label}: CFrame rotation must be orthonormal")
        determinant = (x[0]*(y[1]*z[2]-y[2]*z[1])
                       - x[1]*(y[0]*z[2]-y[2]*z[0])
                       + x[2]*(y[0]*z[1]-y[1]*z[0]))
        if abs(determinant - 1.0) > 0.004:
            raise ValueError(f"{label}: mirrored CFrame is not allowed")
        group = part["collisionGroup"]
        if not isinstance(group, str) or not GROUP.fullmatch(group):
            raise ValueError(f"{label}: invalid collision group")
        for key in ("canQuery", "canTouch"):
            if type(part[key]) is not bool:
                raise ValueError(f"{label}.{key} must be boolean")
        parts.append({"id": identifier, "name": name, "shape": shape, "size": size,
                      "localCFrame": frame, "collisionGroup": group,
                      "canQuery": part["canQuery"], "canTouch": part["canTouch"]})
    parts.sort(key=lambda p: p["id"])
    return {"schemaVersion": 1, "pivot": "Model:GetPivot()", "parts": parts}


def latest(store, slug: str) -> dict | None:
    if not SLUG.fullmatch(slug):
        raise ValueError("invalid Location Asset slug")
    with store.connect() as connection:
        row = connection.execute(
            "SELECT revision, blueprint_json, sha256, captured_at "
            "FROM location_asset_collision_blueprints WHERE asset_slug=? "
            "ORDER BY revision DESC LIMIT 1", (slug,)).fetchone()
    if row is None:
        return None
    return {"revision": row["revision"], "blueprint": json.loads(row["blueprint_json"]),
            "sha256": row["sha256"], "capturedAt": row["captured_at"]}


def save(store, slug: str, payload: dict) -> dict:
    if not SLUG.fullmatch(slug) or not isinstance(payload, dict) or set(payload) != {"blueprint", "expectedRevision"}:
        raise ValueError("invalid Collision Blueprint request")
    expected = payload["expectedRevision"]
    if type(expected) is not int or expected < 0:
        raise ValueError("expectedRevision must be nonnegative integer")
    blueprint = validate(payload["blueprint"], slug=slug)
    raw = json.dumps(blueprint, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    with store.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        if not connection.execute("SELECT 1 FROM location_assets WHERE slug=?", (slug,)).fetchone():
            raise ValueError("unknown Location Asset")
        row = connection.execute("SELECT revision,sha256 FROM location_asset_collision_blueprints "
                                 "WHERE asset_slug=? ORDER BY revision DESC LIMIT 1", (slug,)).fetchone()
        revision = row["revision"] if row else 0
        if revision != expected:
            raise ValueError("Collision Blueprint changed since Capture opened; refresh")
        if not (row and row["sha256"] == digest):
            connection.execute("INSERT INTO location_asset_collision_blueprints "
                               "(asset_slug, revision, blueprint_json, sha256, captured_at) VALUES (?,?,?,?,?)",
                               (slug, revision + 1, raw, digest, time.time()))
    return latest(store, slug)
