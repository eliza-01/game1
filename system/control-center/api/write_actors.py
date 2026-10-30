"""Actor, equipment and publication write operations. No HTTP, persistence, or Studio ownership.

Dependencies are supplied by the composition root; unhandled paths return None.
"""
from urllib.parse import unquote
from . import character_components
from services.character_registration_flow import run as run_character_registration_flow


def route(path, body, deps):
    if not path.startswith(('/api/characters', '/api/weapons', '/api/npcs', '/api/monsters', '/api/npc-equipment',)):
        return None

    response = character_components.write(path, body, deps)
    if response is not None:
        return response
    if path == '/api/characters/assemblies':
        try:
            return 200, deps['character_assemblies'].save(body())
        except ValueError as error:
            return 400, {'error': str(error)}

    def out(status, payload):
        return status, payload

    character_identity = deps["character_identity"]
    monsters = deps["monsters"]
    npc_equipment = deps["npc_equipment"]
    npcs = deps["npcs"]
    publication_credentials = deps["publication_credentials"]
    store = deps["store"]
    sync_character_to_studio = deps["sync_character_to_studio"]
    sync_monster_to_studio = deps["sync_monster_to_studio"]
    sync_weapon_to_studio = deps["sync_weapon_to_studio"]
    weapons = deps["weapons"]

    if path == "/api/characters/workflow":
        # One request owns the ordered checkpoints; partial outcomes are returned
        # as a structured report instead of hiding successful remote uploads.
        return out(200, run_character_registration_flow(
            body(), store=store,
            publication_credentials=publication_credentials,
            sync_character_to_studio=sync_character_to_studio,
        ))

    if path == "/api/characters":
        try:
            return out(200, store.register(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/weapons":
        try:
            return out(200, weapons.register(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/weapons/attack-movement":
        try:
            return out(200, weapons.update_attack_movement(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/npcs":
        try:
            return out(200, npcs.register(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/monsters":
        try:
            return out(200, monsters.register(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/npc-equipment":
        try:
            payload = body()
            return out(200, npc_equipment.set_loadout(
                str(payload.get("npcSlug") or ""),str(payload.get("right") or ""),str(payload.get("left") or "")))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/npc-equipment/sync":
        try:
            slug = str(body().get("npcSlug") or "").strip().lower()
            if not npcs.get(slug):
                raise ValueError("unknown NPC: " + slug)
            loadout = npc_equipment.snapshot(slug)["loadout"]
            synced = []
            for weapon_slug in sorted({loadout["right"], loadout["left"]} - {""}):
                sync_weapon_to_studio(weapon_slug)
                synced.append(weapon_slug)
            return out(200, {"ok": True, "weapons": synced})
        except Exception as error:
            return out(400, {"error": str(error)})

    prefix = "/api/characters/"

    identity_suffix = "/identity"

    stats_suffix = "/stats"

    replace_model_suffix = "/replace-model"

    model_suffix = "/model"

    activate_suffix = "/activate"

    publish_suffix = "/publish"

    sync_suffix = "/sync"

    if path.startswith(prefix) and path.endswith(stats_suffix):
        character_id = unquote(path[len(prefix):-len(stats_suffix)].strip("/"))
        try:
            return out(200, store.set_stats(character_id, body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path.startswith(prefix) and path.endswith(identity_suffix):
        character_id = unquote(path[len(prefix):-len(identity_suffix)].strip("/"))
        try:
            return out(200, character_identity.update(character_id, body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path.startswith(prefix) and path.endswith(replace_model_suffix):
        character_id = unquote(path[len(prefix):-len(replace_model_suffix)].strip("/"))
        try:
            payload = body()
            source_path = str(payload.get("sourcePath") or "").strip()
            if not source_path:
                raise ValueError("choose a replacement FBX first")
            before = store.get(character_id)
            if not before:
                raise ValueError(f"unknown character archetype: {character_id}")
            previous_asset_id = str(before.get("model_asset_id") or "").strip()

            # Stage/analyze the new canonical FBX while the old Roblox asset
            # remains assigned. publish() creates a NEW asset for changed
            # character content and switches the archetype id only on success.
            store.register({
                "existingId": character_id,
                "id": character_id,
                "displayName": before.get("display_name") or "",
                "race": before.get("race") or "",
                "gender": before.get("gender") or "",
                "sourcePath": source_path,
                # Replace is explicit user intent. Never collapse it into the
                # unchanged-content no-op used by ordinary Publish.
                "forceReplacement": True,
            })
            credentials = publication_credentials(str(payload.get("description") or "game1 character model"))
            published = store.publish(character_id, credentials)
            result = {"character": published, "studio": None, "studioError": ""}
            try:
                synced = sync_character_to_studio(character_id)
                result["studio"] = synced.get("studio")
            except Exception as studio_error:
                # Publication already succeeded and the new asset id is now
                # canonical. Do not report the whole replacement as failed
                # merely because Studio refresh needs a retry.
                result["studioError"] = str(studio_error)
            result["previousAssetId"] = previous_asset_id
            result["newAssetId"] = str(published.get("model_asset_id") or "")
            result["assetReplaced"] = bool(
                result["newAssetId"] and result["newAssetId"] != previous_asset_id
            )
            if previous_asset_id and not result["assetReplaced"]:
                raise RuntimeError(
                    "replace model did not create a new Roblox asset id; old asset remains assigned"
                )
            return out(200, result)
        except Exception as error:
            return out(400, {"error": str(error)})

    if path.startswith(prefix) and path.endswith(model_suffix):
        character_id = unquote(path[len(prefix):-len(model_suffix)].strip("/"))
        try:
            payload = body()
            source_character_id = str(payload.get("sourceCharacterId") or "").strip().lower()
            return out(200, store.assign_model(character_id, source_character_id))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path.startswith(prefix) and path.endswith(activate_suffix):
        character_id = unquote(path[len(prefix):-len(activate_suffix)].strip("/"))
        try:
            return out(200, store.set_active(character_id))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path.startswith(prefix) and path.endswith(publish_suffix):
        character_id = unquote(path[len(prefix):-len(publish_suffix)].strip("/"))
        try:
            payload = body()
            credentials = publication_credentials(str(payload.get("description") or ""))
            row = store.publish(character_id, credentials)
            return out(200, sync_character_to_studio(str(row["id"])))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path.startswith(prefix) and path.endswith(sync_suffix):
        character_id = unquote(path[len(prefix):-len(sync_suffix)].strip("/"))
        try:
            return out(200, sync_character_to_studio(character_id))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/characters/active/clear":
        return out(200, store.clear_active())

    if path.startswith("/api/npcs/"):
        slug, _, action = unquote(path[len("/api/npcs/"):]).rpartition("/")
        try:
            if action == "publish":
                credentials = publication_credentials(str(body().get("description") or "game1 npc"))
                return out(200, npcs.publish(slug, credentials))
            if action == "sync":
                return out(200, sync_monster_to_studio(slug, kind="npc"))
        except Exception as error:
            return out(400, {"error": str(error)})

    monster_prefix = "/api/monsters/"

    monster_publish_suffix = "/publish"

    monster_sync_suffix = "/sync"

    if path.startswith(monster_prefix) and path.endswith(monster_publish_suffix):
        slug = unquote(path[len(monster_prefix):-len(monster_publish_suffix)].strip("/"))
        try:
            payload = body()
            credentials = publication_credentials(str(payload.get("description") or "game1 monster"))
            return out(200, monsters.publish(slug, credentials))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path.startswith(monster_prefix) and path.endswith(monster_sync_suffix):
        slug = unquote(path[len(monster_prefix):-len(monster_sync_suffix)].strip("/"))
        try:
            return out(200, sync_monster_to_studio(slug))
        except Exception as error:
            return out(400, {"error": str(error)})

    weapon_prefix = "/api/weapons/"

    weapon_publish_suffix = "/publish"

    weapon_sync_suffix = "/sync"

    weapon_activate_suffix = "/activate"

    if path.startswith(weapon_prefix) and path.endswith(weapon_publish_suffix):
        slug = unquote(path[len(weapon_prefix):-len(weapon_publish_suffix)].strip("/"))
        try:
            payload = body()
            credentials = publication_credentials(str(payload.get("description") or "game1 weapon"))
            return out(200, weapons.publish(slug, credentials))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path.startswith(weapon_prefix) and path.endswith(weapon_sync_suffix):
        slug = unquote(path[len(weapon_prefix):-len(weapon_sync_suffix)].strip("/"))
        try:
            return out(200, sync_weapon_to_studio(slug))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path.startswith(weapon_prefix) and path.endswith(weapon_activate_suffix):
        slug = unquote(path[len(weapon_prefix):-len(weapon_activate_suffix)].strip("/"))
        try:
            return out(200, weapons.set_active(slug))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/weapons/active/clear":
        return out(200, weapons.clear_active())
    return None
