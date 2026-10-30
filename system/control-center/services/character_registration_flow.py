"""Single user-facing character registration/publication workflow.

Open Cloud and Studio are independent external systems: they cannot be committed
atomically with SQLite. Preserve the last published asset until a new upload
succeeds and report each checkpoint, including partial success. Never rollback a
successful remote upload or silently claim Studio sync succeeded.
"""


from threading import Lock

_pipeline_guard = Lock()
_active_characters = set()


def run(payload, *, store, publication_credentials, sync_character_to_studio):
    """Reject overlapping operations for the same character (e.g. two browser tabs)."""
    key = str(payload.get("existingId") or payload.get("id") or "").strip().lower()
    with _pipeline_guard:
        if key in _active_characters:
            return {"ok": False, "characterId": key, "newAssetId": "", "stages": [
                {"name": "validate", "status": "error", "detail": "Another Reg + Publish is in progress for this character"}],
                "failedStage": "validate", "error": "Another Reg + Publish is in progress",
                "recovery": "Wait for the current operation to complete; do not publish twice."}
        _active_characters.add(key)
    try:
        return _run_unlocked(payload, store=store,
                             publication_credentials=publication_credentials,
                             sync_character_to_studio=sync_character_to_studio)
    finally:
        with _pipeline_guard:
            _active_characters.discard(key)


def _run_unlocked(payload, *, store, publication_credentials, sync_character_to_studio):
    stages = []
    result = {"ok": False, "stages": stages, "characterId": "", "previousAssetId": "", "newAssetId": "", "studio": None}
    phase = "validate"

    def completed(name, message):
        stages.append({"name": name, "status": "ok", "detail": message})

    try:
        existing_id = str(payload.get("existingId") or "").strip().lower()
        before = store.get(existing_id) if existing_id else None
        if existing_id and before is None:
            raise ValueError("selected character no longer exists; refresh the page")
        character_id = existing_id or str(payload.get("id") or "").strip().lower()
        source = str(payload.get("sourcePath") or "").strip()
        if before:
            if any((
                ("id" in payload and str(payload["id"]).strip().lower() != existing_id),
                ("race" in payload and str(payload["race"]).strip().lower() != before["race"]),
                ("gender" in payload and str(payload["gender"]).strip().lower() != before["gender"]),
                ("displayName" in payload and str(payload["displayName"]).strip() != before["display_name"]),
            )):
                raise ValueError("save identity separately before Reg + Publish")
            if before.get("model_asset_id") and not source and not before.get("model_replacement_pending") and before.get("status") == "PUBLISHED":
                raise ValueError("choose a replacement FBX; the currently published model is unchanged")
        elif not source:
            raise ValueError("choose an FBX before registering a new character")

        # Validate Open Cloud settings before changing the local registry.
        credentials = publication_credentials(str(payload.get("description") or "game1 character model"))
        completed("validate", "Identity and Open Cloud credentials accepted")

        result["previousAssetId"] = str(before.get("model_asset_id") or "") if before else ""
        phase = "register"
        if source or not before:
            registration = {
                "existingId": existing_id,
                "id": character_id,
                "race": payload.get("race"), "gender": payload.get("gender"),
                "displayName": payload.get("displayName"),
                "sourcePath": source,
            }
            if not before:
                registration["stats"] = payload.get("stats") or {}
            if before and before.get("model_asset_id"):
                registration["forceReplacement"] = True
            row = store.register(registration)
            completed("register", f"FBX analyzed; canonical source and revision {row['revision']} saved")
        else:
            row = before
            completed("register", "Existing canonical FBX reused; no duplicate registration")
        result["characterId"] = str(row["id"])

        phase = "publish"
        published = store.publish(character_id, credentials)
        result["newAssetId"] = str(published.get("model_asset_id") or "")
        if result["previousAssetId"] and source and result["newAssetId"] == result["previousAssetId"]:
            raise RuntimeError("replace model did not create a new Roblox asset id; old asset remains assigned")
        completed("publish", f"Roblox Model Asset {result['newAssetId']} committed to registry")

        phase = "studio"
        synced = sync_character_to_studio(character_id)
        result["studio"] = synced.get("studio")
        completed("studio", "Studio Bridge confirmed model sync and rig validation")
        result["ok"] = True
    except Exception as error:
        result["failedStage"] = phase
        result["error"] = str(error)
        stages.append({"name": phase, "status": "error", "detail": str(error)})
        if result["newAssetId"]:
            result["recovery"] = "Model ID is committed. Retry Studio sync; do not republish."
        elif result["characterId"]:
            result["recovery"] = "Registration is saved, but publication did not complete. Reopen this character to retry."
        else:
            result["recovery"] = "Nothing was published. Correct the issue and retry."
    return result
