"""Published-model synchronization into Roblox Studio.

Independent of HTTP, publication, database connections and native file dialogs.
All storage and Bridge I/O arrive through constructor injection.
"""
import json
from .studio_rig_validation import validate_published_rig
from .texture_alpha import texture_binding


class StudioAssetSyncService:
    def __init__(self, characters, weapons, monsters, npcs, load_model):
        self._characters = characters
        self._weapons = weapons
        self._monsters = monsters
        self._npcs = npcs
        self._load_model = load_model

    def sync_character_to_studio(self, character_id: str):
        row = self._characters.get(character_id)
        if not row:
            raise ValueError(f"unknown character archetype: {character_id}")
        asset_id = str(row.get("model_asset_id") or "").strip()
        if not asset_id:
            raise ValueError("publish the character model before syncing it to Studio")
        destination = [
            "characters",
            str(row.get("race") or ""),
            str(row.get("gender") or ""),
            str(row.get("id") or ""),
            "model",
        ]
        result = self._load_model(asset_id, destination, wrapper_name=str(row.get("id") or ""))
        validate_published_rig(result, row, kind="character")
        return {"character": row, "studio": result}


    def sync_weapon_to_studio(self, slug: str):
        row = self._weapons.get(slug)
        if not row:
            raise ValueError(f"unknown weapon: {slug}")
        asset_id = str(row.get("model_asset_id") or "").strip()
        if not asset_id:
            raise ValueError("publish the weapon model before syncing it to Studio")
        texture_assets = [
            texture_binding(item.get("slot") or "", item.get("asset_id") or "",
                            getattr(self._weapons, "root", None), item.get("source_path") or "",
                            registered_sha256=item.get("sha256") or "",
                            published_sha256=item.get("published_sha256") or "")
            for item in (row.get("textures") or [])
            if str(item.get("asset_id") or "").isdigit()
        ]
        destination = ["weapons", str(row.get("storage_type") or row.get("weapon_type") or ""), str(row.get("slug") or ""), "model"]
        result = self._load_model(
            asset_id,
            destination,
            wrapper_name=str(row.get("slug") or ""),
            placement_mode="weapon-pivot",
            metadata={
                "weaponSlug": str(row.get("slug") or ""),
                "weaponType": str(row.get("weapon_type") or ""),
                "rarity": str(row.get("rarity") or ""),
                "textures": texture_assets,
            },
        )
        return {"weapon": row, "studio": result}

    def sync_monster_to_studio(self, slug: str, kind: str = "monster"):
        actor_store = self._npcs if kind == "npc" else self._monsters
        row = actor_store.get(slug)
        if not row:
            raise ValueError(f"unknown {kind}: {slug}")
        asset_id = str(row.get("model_asset_id") or "").strip()
        if not asset_id:
            raise ValueError(f"publish the {kind} model before syncing it to Studio")
        texture_assets = [
            texture_binding(item.get("slot") or "", item.get("asset_id") or "",
                            getattr(actor_store, "root", None), item.get("source_path") or "",
                            registered_sha256=item.get("sha256") or "",
                            published_sha256=item.get("published_sha256") or "")
            for item in (row.get("textures") or [])
            if str(item.get("asset_id") or "").isdigit()
        ]
        destination = [f"{kind}s", str(row.get("slug") or ""), "model"]
        result = self._load_model(
            asset_id,
            destination,
            wrapper_name=str(row.get("slug") or ""),
            placement_mode="monster-rig",
            metadata={
                "monsterSlug": str(row.get("slug") or ""),
                "entityKind": kind,
                "expectedBones": [
                    str(item.get("name"))
                    for item in json.loads(str(row.get("skeleton_json") or "{}" )).get("bones", [])
                    if str(item.get("name") or "")
                ],
                "textures": texture_assets,
            },
        )
        validate_published_rig(result, row, kind="monster")

        texture_stats = ((result.get("monsterStats") or {}).get("textures") or {})
        if texture_assets and int(texture_stats.get("applied") or 0) <= 0:
            raise ValueError("Studio loaded the monster rig but did not apply any published monster textures")
        return {"monster": row, "studio": result}
