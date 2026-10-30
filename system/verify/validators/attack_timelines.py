"""Attack Timeline data, damage windows and authoring contract (M168)."""

import json
from pathlib import Path
from typing import Callable


def check_attack_timelines(root: Path, report_error: Callable[[str], None], *,
                           attack_timeline_text: str, attack_timeline_data_text: str,
                           studio_plugin_text: str, host_agent_text: str):
    """Return shared Asset Manager UI and Studio Bridge source text."""
    # m38 character attack damage policy. Character attacks use an authored
    # HitStart -> HitEnd interval. The old terminal Hit/result dispatch and pose
    # buffer are removed; monsters intentionally keep their single Hit checkpoint.
    attack_timeline_manifest_path = root / "assets/manifests/attack-timelines.json"
    attack_timeline_manifest = json.loads(attack_timeline_manifest_path.read_text(encoding="utf-8")) if attack_timeline_manifest_path.is_file() else {}
    if int(attack_timeline_manifest.get("schemaVersion") or 0) != 2:
        report_error("m38 attack timeline manifest must use schemaVersion 2")
    attack_timeline_rows = {str(row.get("clipId") or ""): row for row in attack_timeline_manifest.get("timelines") or []}
    for clip_id in [
        "human_female__weapon__1hs__attack__01",
        "human_female__weapon__1hs__attack__02",
        "human_female__weapon__1hs__attack__03",
    ]:
        row = attack_timeline_rows.get(clip_id)
        if not row:
            report_error(f"m38 character timeline clip missing {clip_id}")
            continue
        events = row.get("events") or {}
        if "HitStart" not in events or "HitEnd" not in events:
            report_error(f"m38 {clip_id} requires HitStart and HitEnd")
        if "Hit" in events:
            report_error(f"m38 {clip_id} must not keep obsolete character Hit damage event")
        if float((events.get("HitStart") or {}).get("normalizedTime") or 0) > float((events.get("HitEnd") or {}).get("normalizedTime") or 0):
            report_error(f"m38 {clip_id} HitStart cannot be after HitEnd")
    monster_timeline = attack_timeline_rows.get("monster__gremlin__attack__01") or {}
    monster_events = monster_timeline.get("events") or {}
    if "Hit" not in monster_events or "HitStart" in monster_events or "HitEnd" in monster_events:
        report_error("m38 monster timeline must retain only its single Hit policy")

    character_window_path = root / "src/shared/combat/CharacterAttackWindow.luau"
    character_window_text = character_window_path.read_text(encoding="utf-8") if character_window_path.is_file() else ""
    for required in ["CharacterAttackWindow.Resolve", "events and events.HitStart", "events and events.HitEnd", "startTime", "endTime"]:
        if required not in character_window_text:
            report_error(f"m38 character damage-window policy missing {required}")

    attack_controller_m38 = (root / "src/client/combat/AttackController.luau").read_text(encoding="utf-8")
    for required in [
        "CharacterAttackWindow.Resolve(action.timeline)",
        "damageWindow.startTime",
        "damageWindow.endTime",
        "activePoseFrom = activePoseStartedAt + damagePoseStart",
        "activePoseUntil = activePoseStartedAt + damagePoseEnd",
    ]:
        if required not in attack_controller_m38:
            report_error(f"m38 client HitStart/HitEnd pose window missing {required}")

    attack_service_m38 = (root / "src/server/combat/AttackService.luau").read_text(encoding="utf-8")
    for required in [
        "session.damageWindow",
        "CharacterAttackWindow.Resolve(timing)",
        'SetAttribute("AttackDamageStartsAt"',
        'SetAttribute("AttackDamageEndsAt"',
        "elapsed + 1e-4 < damageWindow.startTime",
        "elapsed > damageWindow.endTime + 1e-4",
        "AttackSessionStore.EnsureSweep",
    ]:
        if required not in attack_service_m38:
            report_error(f"m38 server HitStart/HitEnd damage gate missing {required}")
    for forbidden in [
        "activeDamageUntil",
        "activeDamageCutoffElapsed",
        "activeDamageStartElapsed",
        "meleeDamageWindow",
        "scheduleTimelineResults",
        "resolveMeleeDamage",
        "validatedAnimatedWeaponVolume",
        "weaponPoseBuffers",
        "lastDamageElapsed",
    ]:
        if forbidden in attack_service_m38:
            report_error(f"m38 obsolete terminal-Hit/pose-buffer path remains: {forbidden}")

    # m35 Attack Timeline authoring is owned by Asset Manager. Studio only previews
    # the published rig/animation and sends confirmed normalized event points back.
    timeline_store_text = (root / "system/control-center/timeline_store.py").read_text(encoding="utf-8")
    timeline_js_text = (root / "system/control-center/static/timelines.js").read_text(encoding="utf-8")
    index_m35_text = (root / "system/control-center/static/index.html").read_text(encoding="utf-8")
    studio_bridge_m35_text = (root / "system/control-center/studio_bridge.py").read_text(encoding="utf-8")
    for required in [
        '"schemaVersion": 2',
        '"project": "game1"',
        '"timelines"',
    ]:
        if required not in attack_timeline_manifest_path.read_text(encoding="utf-8"):
            report_error(f"m35 attack timeline manifest missing {required}")
    for required in [
        'require(script.Parent:WaitForChild("AttackTimelineData"))',
        "AttackTimelineConfig.ByClip = BY_CLIP",
    ]:
        if required not in attack_timeline_text:
            report_error(f"m35 runtime timeline resolver missing {required}")
    for required in [
        "class TimelineStore",
        "begin_editor_session",
        "update_editor_state",
        "export_runtime",
        "attack-timelines.json",
        "AttackTimelineData.luau",
    ]:
        if required not in timeline_store_text:
            report_error(f"m35 timeline store missing {required}")
    for required in ["EVENT_CATALOGS", '"characters"', '"HitStart"', '"HitEnd"', '"monsters"', '"Hit"', "event_catalog_for_subject"]:
        if required not in timeline_store_text:
            report_error(f"m38 subject-specific timeline catalog missing {required}")
    for forbidden in ["Hit2", "projectile_release", '"result"']:
        if forbidden in timeline_store_text:
            report_error(f"m38 obsolete generic timeline event plumbing remains: {forbidden}")
    if "eventCatalogs" not in timeline_js_text:
        report_error("m38 Asset Manager must render the subject-specific event catalog")
    for required in [
        'id="nav-timelines"',
        'id="timelines-view"',
        'id="timeline-open-studio"',
        'timelines.js?v=2',
    ]:
        if required not in index_m35_text:
            report_error(f"m35 Asset Manager timeline UI missing {required}")
    for required in [
        "/api/timelines/open",
        "/api/timelines/editor-state",
        "/api/timelines/save",
        "setInterval(timelinePoll,700)",
    ]:
        if required not in timeline_js_text:
            report_error(f"m35 Asset Manager timeline behavior missing {required}")
    for required in [
        "run_timeline_editor_bridge",
        '"command": "timeline-editor"',
        '"/timeline-editor-result"',
    ]:
        if required not in studio_bridge_m35_text:
            report_error(f"m35 Studio timeline bridge missing {required}")
    for required in [
        "Game1AttackTimeline_v2",
        "handleTimelineEditor",
        "Confirm point",
        'AGENT_BASE_URL .. "/api/timelines/editor-event"',
    ]:
        if required not in studio_plugin_text:
            report_error(f"m35 Studio Attack Timeline plugin missing {required}")

    # m37 follows the RobloxLineage Attack Options preview model: the selected rig lives
    # inside a ViewportFrame/WorldModel and the fetched KeyframeSequence is sampled directly
    # onto Bone/Motor6D.Transform. Timeline authoring no longer depends on AnimationTrack
    # playback in edit-mode Workspace.
    for required in [
        'game:GetService("AnimationClipProvider")',
        'game:GetService("TweenService")',
        'Instance.new("ViewportFrame")',
        'Instance.new("WorldModel")',
        'TimelinePreviewWorld',
        'buildTimelinePoseTracks',
        'sampleTimelineTrack',
        'applyTimelinePose',
        'AnimationClipProvider:GetAnimationClipAsync',
        'clip:IsA("KeyframeSequence")',
        'preview.Parent = timelineWorld',
        'model bridge v24',
    ]:
        if required not in studio_plugin_text:
            report_error(f"m37 in-plugin timeline preview missing {required}")
    for removed in [
        "timelineFreezeTrackAt",
        "track.TimePosition",
        "timelineEditor.track",
        "preview.Parent = Workspace",
    ]:
        if removed in studio_plugin_text:
            report_error(f"m37 Studio timeline still contains obsolete Workspace/AnimationTrack preview code: {removed}")
    for required in [
        '"/api/timelines"',
        'path == "/api/timelines/open"',
        'path == "/api/timelines/editor-event"',
        'path == "/api/timelines/save"',
    ]:
        if required not in host_agent_text:
            report_error(f"m35 host agent timeline API missing {required}")
    for clip_id in [
        "human_female__weapon__1hs__attack__01",
        "human_female__weapon__1hs__attack__02",
        "human_female__weapon__1hs__attack__03",
        "monster__gremlin__attack__01",
    ]:
        if clip_id not in attack_timeline_data_text:
            report_error(f"m35 generated runtime timeline is missing {clip_id}")
    return index_m35_text, studio_bridge_m35_text
