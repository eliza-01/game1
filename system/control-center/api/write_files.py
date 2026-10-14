"""Local picker and file-export write operations. No HTTP, persistence, or Studio ownership.

Dependencies are supplied by the composition root; unhandled paths return None.
"""
from urllib.parse import unquote


def route(path, body, deps):
    if not path.startswith(('/api/files/', '/api/animation-export/',)):
        return None

    def out(status, payload):
        return status, payload

    choose_animation_folder = deps["choose_animation_folder"]
    choose_character_fbx = deps["choose_character_fbx"]
    choose_location_asset_fbx = deps["choose_location_asset_fbx"]
    choose_location_asset_texture = deps["choose_location_asset_texture"]
    choose_monster_fbx = deps["choose_monster_fbx"]
    choose_monster_textures = deps["choose_monster_textures"]
    choose_weapon_fbx = deps["choose_weapon_fbx"]
    choose_weapon_textures = deps["choose_weapon_textures"]
    write_animation_export = deps["write_animation_export"]

    if path == "/api/animation-export/write":
        try:
            return out(200, write_animation_export(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/files/choose-character-model":
        try:
            return out(200, {"path": choose_character_fbx()})
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/files/choose-animation-folder":
        try:
            payload = body()
            return out(200, {"path": choose_animation_folder(str(payload.get("initialPath") or ""))})
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/files/choose-npc-model":
        try:
            return out(200, {"path": choose_monster_fbx()})
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/files/choose-npc-textures":
        try:
            return out(200, {"paths": choose_monster_textures()})
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/files/choose-monster-model":
        try:
            return out(200, {"path": choose_monster_fbx()})
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/files/choose-monster-textures":
        try:
            return out(200, {"paths": choose_monster_textures()})
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/files/choose-weapon-model":
        try:
            return out(200, {"path": choose_weapon_fbx()})
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/files/choose-weapon-textures":
        try:
            return out(200, {"paths": choose_weapon_textures()})
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/files/choose-location-asset-model":
        try:
            return out(200, {"path": choose_location_asset_fbx()})
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/files/choose-location-asset-texture":
        try:
            return out(200, {"path": choose_location_asset_texture()})
        except Exception as error:
            return out(400, {"error": str(error)})
    return None
