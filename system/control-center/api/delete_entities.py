"""Entity/binding retirement routes; preserve store-owned archive behavior.

No direct HTTP transport dependency. Deletion ordering remains unchanged.
"""
from urllib.parse import unquote


def route(path, body, deps):
    if not path.startswith(('/api/animation-bindings/', '/api/npc-animation-bindings/', '/api/npcs/', '/api/monster-animation-bindings/', '/api/monsters/', '/api/location-assets/', '/api/weapons/', '/api/characters/', '/api/real-estate/',)):
        return None

    def out(status, payload):
        return status, payload

    if path.startswith('/api/real-estate/'):
        slug = unquote(path[len('/api/real-estate/'):].strip('/'))
        try:
            job = deps['real_estate_publications'].get(slug)
            if job and job['status'] in ('queued', 'running'):
                raise ValueError('house publication is running; wait until it completes')
            return out(200, deps['real_estate'].delete(slug))
        except (ValueError, OSError, KeyError) as error:
            return out(400, {'error': str(error)})


    animations = deps["animations"]
    location_assets = deps["location_assets"]
    monster_animations = deps["monster_animations"]
    monster_spawns = deps["monster_spawns"]
    monsters = deps["monsters"]
    npc_animations = deps["npc_animations"]
    npc_equipment = deps["npc_equipment"]
    npc_spawns = deps["npc_spawns"]
    npcs = deps["npcs"]
    store = deps["store"]
    weapons = deps["weapons"]

    binding_prefix = "/api/animation-bindings/"

    if path.startswith(binding_prefix):
        try:
            return out(200, animations.delete_binding(unquote(path[len(binding_prefix):])))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path.startswith("/api/npc-animation-bindings/"):
        try:
            return out(200, npc_animations.delete_binding(unquote(path[len("/api/npc-animation-bindings/"):])))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path.startswith("/api/npcs/"):
        slug = unquote(path[len("/api/npcs/"):])
        try:
            used = npc_spawns.monster_usage(slug)
            if used:
                raise ValueError("delete NPC spawn points first: " + ", ".join(used[:8]))
            npc_animations.delete_profile(slug)
            npcs.delete(slug)
            npc_equipment.delete(slug)
            return out(200, {"ok": True})
        except Exception as error:
            return out(400, {"error": str(error)})

    monster_binding_prefix = "/api/monster-animation-bindings/"

    if path.startswith(monster_binding_prefix):
        try:
            return out(200, monster_animations.delete_binding(unquote(path[len(monster_binding_prefix):])))
        except Exception as error:
            return out(400, {"error": str(error)})

    monster_prefix = "/api/monsters/"

    if path.startswith(monster_prefix):
        slug = unquote(path[len(monster_prefix):])
        try:
            spawn_ids = monster_spawns.monster_usage(slug)
            if spawn_ids:
                raise ValueError("delete monster spawns first: " + ", ".join(spawn_ids[:8]))
            monster_animations.delete_profile(slug)
            monsters.delete(slug)
            return out(200, {"ok": True})
        except Exception as error:
            return out(400, {"error": str(error)})

    location_asset_prefix = "/api/location-assets/"

    if path.startswith(location_asset_prefix):
        slug = unquote(path[len(location_asset_prefix):])
        try:
            location_assets.delete(slug)
            return out(200, {"ok": True})
        except Exception as error:
            return out(400, {"error": str(error)})

    weapon_prefix = "/api/weapons/"

    if path.startswith(weapon_prefix):
        slug = unquote(path[len(weapon_prefix):])
        try:
            users = npc_equipment.users_of_weapon(slug)
            if users:
                raise ValueError("weapon is equipped by NPC(s): " + ", ".join(users) + "; unequip before deleting")
            weapons.delete(slug)
            return out(200, {"ok": True})
        except Exception as error:
            return out(400, {"error": str(error)})

    prefix = "/api/characters/"

    if path.startswith(prefix):
        character_id = unquote(path[len(prefix):])
        try:
            usage = animations.character_usage(character_id)
            if usage["clips"] or usage["bindings"]:
                raise ValueError(
                    f"delete the character animation profile first: {usage['clips']} clip(s), {usage['bindings']} binding(s)"
                )
            store.delete(character_id)
            animations.delete_empty_profile(character_id)
            return out(200, {"ok": True})
        except Exception as error:
            return out(400, {"error": str(error)})
    return None
