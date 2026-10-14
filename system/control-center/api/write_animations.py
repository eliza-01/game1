"""Animation binding and publication write operations. No HTTP, persistence, or Studio ownership.

Dependencies are supplied by the composition root; unhandled paths return None.
"""
from urllib.parse import unquote


def route(path, body, deps):
    if not path.startswith(('/api/animation-speed-scaling', '/api/animations', '/api/monster-animations', '/api/npc-animations', '/api/npc-animation-bindings', '/api/monster-animation-bindings', '/api/animation-bindings',)):
        return None

    def out(status, payload):
        return status, payload

    animation_speed_scaling = deps["animation_speed_scaling"]
    animations = deps["animations"]
    monster_animations = deps["monster_animations"]
    npc_animations = deps["npc_animations"]
    publication_credentials = deps["publication_credentials"]

    if path == "/api/animation-speed-scaling/custom":
        try:
            return out(200, animation_speed_scaling.save_custom(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/animation-speed-scaling":
        try:
            return out(200, animation_speed_scaling.update(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/animations/check-roblox-assets":
        try:
            credentials = publication_credentials()
            character = animations.check_manual_reimports(credentials)
            monster = monster_animations.check_manual_reimports(credentials)
            npc = npc_animations.check_manual_reimports(credentials)
            return out(200, {
                "schemaVersion": 1,
                "project": "game1",
                "requested": int(character.get("requested") or 0) + int(monster.get("requested") or 0) + int(npc.get("requested") or 0),
                "confirmed": int(character.get("confirmed") or 0) + int(monster.get("confirmed") or 0) + int(npc.get("confirmed") or 0),
                "pending": int(character.get("pending") or 0) + int(monster.get("pending") or 0) + int(npc.get("pending") or 0),
                "failed": int(character.get("failed") or 0) + int(monster.get("failed") or 0) + int(npc.get("failed") or 0),
                "character": character,
                "monster": monster,
                "npc": npc,
            })
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/monster-animations/scan":
        try:
            payload = body()
            return out(200, monster_animations.scan_folder(str(payload.get("monsterSlug") or ""), str(payload.get("rootPath") or "")))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/monster-animations/assign":
        try:
            payload = body()
            return out(200, monster_animations.assign_file(
                str(payload.get("monsterSlug") or ""), str(payload.get("sourcePath") or ""),
                str(payload.get("slot") or ""), int(payload.get("variant") or 0),
            ))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/npc-animations/scan":
        try:
            payload = body()
            return out(200, npc_animations.scan_folder(str(payload.get("npcSlug") or ""), str(payload.get("rootPath") or "")))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/npc-animations/assign":
        try:
            payload = body()
            return out(200, npc_animations.assign_file(
                str(payload.get("npcSlug") or ""), str(payload.get("sourcePath") or ""),
                str(payload.get("slot") or ""), int(payload.get("variant") or 0),
                str(payload.get("weaponSet") or "1hs")))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/animations/scan":
        try:
            payload = body()
            return out(200, animations.scan_folder(str(payload.get("characterId") or ""), str(payload.get("rootPath") or "")))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/animations/assign":
        try:
            payload = body()
            return out(200, animations.assign_file(
                str(payload.get("characterId") or ""),
                str(payload.get("sourcePath") or ""),
                str(payload.get("scope") or ""),
                str(payload.get("weaponSet") or ""),
                str(payload.get("slot") or ""),
                int(payload.get("variant") or 0),
            ))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path.startswith("/api/npc-animations/"):
        clip_id, _, action = unquote(path[len("/api/npc-animations/"):]).rpartition("/")
        try:
            payload = body()
            if action == "rename":
                return out(200, npc_animations.rename_npc_binding(
                    clip_id, str(payload.get("weaponSet") or ""), str(payload.get("filename") or "")))
            if action == "publish-missing":
                return out(200, npc_animations.publish_missing(clip_id, publication_credentials(str(payload.get("description") or "game1 npc animation"))))
            if action == "publish":
                return out(200, npc_animations.publish_clip(clip_id, publication_credentials(str(payload.get("description") or "game1 npc animation"))))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path.startswith("/api/npc-animation-bindings/") and path.endswith("/options"):
        try:
            key = unquote(path[len("/api/npc-animation-bindings/"):-len("/options")].strip("/"))
            payload = body()
            return out(200, npc_animations.set_animation_options(
                key, payload.get("compatibleWith"), payload.get("weight"), payload.get("disarm")))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path.startswith("/api/npc-animation-bindings/") and path.endswith("/compatibility"):
        try:
            key = unquote(path[len("/api/npc-animation-bindings/"):-len("/compatibility")].strip("/"))
            return out(200, npc_animations.set_compatibility(key, body().get("compatibleWith")))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path.startswith("/api/npc-animation-bindings/") and path.endswith("/disarm"):
        try:
            key = unquote(path[len("/api/npc-animation-bindings/"):-len("/disarm")].strip("/"))
            return out(200, npc_animations.set_disarm(key, bool(body().get("enabled"))))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path.startswith("/api/npc-animation-bindings/") and path.endswith("/weight"):
        try:
            key = unquote(path[len("/api/npc-animation-bindings/"):-len("/weight")].strip("/"))
            payload = body()
            return out(200, npc_animations.set_weight(key, int(payload.get("weight", 100))))
        except Exception as error:
            return out(400, {"error": str(error)})

    monster_publish_missing_suffix = "/publish-missing"
    monster_animation_prefix = "/api/monster-animations/"

    monster_publish_animation_suffix = "/publish"

    if path.startswith(monster_animation_prefix) and path.endswith(monster_publish_missing_suffix):
        slug = unquote(path[len(monster_animation_prefix):-len(monster_publish_missing_suffix)].strip("/"))
        try:
            payload = body()
            credentials = publication_credentials(str(payload.get("description") or "game1 monster animation"))
            return out(200, monster_animations.publish_missing(slug, credentials))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path.startswith(monster_animation_prefix) and path.endswith(monster_publish_animation_suffix):
        clip_id = unquote(path[len(monster_animation_prefix):-len(monster_publish_animation_suffix)].strip("/"))
        try:
            payload = body()
            credentials = publication_credentials(str(payload.get("description") or "game1 monster animation"))
            return out(200, monster_animations.publish_clip(clip_id, credentials))
        except Exception as error:
            return out(400, {"error": str(error)})

    monster_binding_prefix = "/api/monster-animation-bindings/"

    if path.startswith(monster_binding_prefix) and path.endswith("/weight"):
        binding_id = unquote(path[len(monster_binding_prefix):-len("/weight")].strip("/"))
        try:
            payload = body()
            return out(200, monster_animations.set_weight(binding_id, int(payload.get("weight") or 100)))
        except Exception as error:
            return out(400, {"error": str(error)})

    publish_missing_suffix = "/publish-missing"
    animation_prefix = "/api/animations/"

    publish_animation_suffix = "/publish"

    if path.startswith(animation_prefix) and path.endswith(publish_missing_suffix):
        character_id = unquote(path[len(animation_prefix):-len(publish_missing_suffix)].strip("/"))
        try:
            payload = body()
            credentials = publication_credentials(str(payload.get("description") or "game1 character animation"))
            return out(200, animations.publish_missing(character_id, credentials))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path.startswith(animation_prefix) and path.endswith(publish_animation_suffix):
        clip_id = unquote(path[len(animation_prefix):-len(publish_animation_suffix)].strip("/"))
        try:
            payload = body()
            credentials = publication_credentials(str(payload.get("description") or "game1 character animation"))
            return out(200, animations.publish_clip(clip_id, credentials))
        except Exception as error:
            return out(400, {"error": str(error)})

    binding_prefix = "/api/animation-bindings/"

    weight_suffix = "/weight"

    if path.startswith(binding_prefix) and path.endswith(weight_suffix):
        binding_id = unquote(path[len(binding_prefix):-len(weight_suffix)].strip("/"))
        try:
            payload = body()
            return out(200, animations.set_weight(binding_id, int(payload.get("weight") or 100)))
        except Exception as error:
            return out(400, {"error": str(error)})
    return None
