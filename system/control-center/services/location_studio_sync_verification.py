"""Interpret a read-only Location Studio scan, independently of atlas revisions.

An atlas binding's revision is *not* proof that Place geometry needs Sync.
Only Studio's scoped Find report may establish actionable changes; a current,
complete report can acknowledge the atlas revision without mutating Workspace.
"""
from __future__ import annotations


def classify_scan(report: dict) -> str:
    """Return current, pending, or review_required; never infer from local IDs.

    ``current`` requires no unmanaged historical candidates and no unresolved
    canonical/FBX inspection work. ``pending`` requires at least one *managed*,
    actionable MeshPart with an actual Mesh/Texture/Alpha discrepancy.
    """
    if not isinstance(report, dict) or not isinstance(report.get('parts'), list):
        return 'review_required'
    parts = report['parts']
    actionable = any(
        part.get('managed') is True
        and not part.get('republishRequired', False)
        and not part.get('needsFbxInspection', False)
        and any(part.get(flag) is True for flag in ('needsMesh', 'needsTexture', 'needsAlpha'))
        for part in parts if isinstance(part, dict)
    )
    if actionable:
        return 'pending'

    counters = ('meshPending', 'texturePending', 'alphaPending', 'geometryPending')
    if (report.get('mode') == 'current'
            and report.get('unmanagedMeshParts') == 0
            and all(type(report.get(key)) is int and report[key] == 0 for key in counters)
            and all(isinstance(part, dict) and part.get('managed') is True
                    # Older Studio plugins may omit Alpha/rig flags. Their
                    # reports cannot prove the complete current contract.
                    and all(type(part.get(flag)) is bool for flag in (
                        'needsAlpha', 'alphaCurrent', 'republishRequired',
                        'needsFbxInspection', 'needsCanonicalReplacement'))
                    and not any(part.get(flag) is True for flag in (
                        'needsMesh', 'needsTexture', 'needsAlpha', 'republishRequired',
                        'needsFbxInspection', 'needsCanonicalReplacement'))
                    and part.get('meshCurrent') is True
                    and part.get('textureCurrent') is True
                    and part.get('alphaCurrent', True) is True
                    for part in parts)):
        # Empty parts and zero unmanaged counts mean there are no placements
        # needing changes in this Studio Place. No Replace is warranted.
        return 'current'
    return 'review_required'
