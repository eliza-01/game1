"""Recover immutable publication identity after a Location Asset slug rename.

The authoring database uses the current slug to expose old publications under
one Location Asset.  MySQL asset audit is append-only, however: the key stored
when a publication occurred must never change when authoring metadata is renamed.
"""
from __future__ import annotations


def slug_at_publication(current_slug: str, occurred_at: float,
                        aliases: list[dict]) -> str:
    """Return the slug in use at *occurred_at* without modifying the history.

    After each rename the SQLite alias table holds every old slug pointing at
    the latest one.  Reverse the renames in descending timestamp order.  This
    works for A -> B -> C without guessing from the publication's Mesh/Image ID.
    """
    key = current_slug
    for alias in sorted(aliases, key=lambda row: float(row['renamed_at']), reverse=True):
        if (alias['current_slug'] == current_slug
                and float(occurred_at) < float(alias['renamed_at'])):
            key = str(alias['old_slug'])
    return key
