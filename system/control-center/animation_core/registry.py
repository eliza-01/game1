from __future__ import annotations

import json
import re

from .common import PROJECT, SCHEMA_VERSION, WEAPON_SETS
from .documents import get_document

def lua_data(value):
    if value is None:return 'nil'
    if value is True:return 'true'
    if value is False:return 'false'
    if isinstance(value,(int,float)):return repr(value)
    if isinstance(value,str):return re.sub(r'\\u([0-9a-fA-F]{4})',r'\\u{\1}',json.dumps(value,ensure_ascii=False))
    if isinstance(value,list):return '{'+','.join(lua_data(x) for x in value)+'}'
    return '{'+','.join('['+lua_data(k)+']='+lua_data(v) for k,v in value.items())+'}'


class AnimationRegistryMixin:
    def export(self):
        with self.connect() as connection:
            profiles = [dict(row) for row in connection.execute("SELECT * FROM animation_profiles ORDER BY character_id")]
            clips = [dict(row) for row in connection.execute("SELECT * FROM animation_clips ORDER BY character_id,name")]
            bindings = [dict(row) for row in connection.execute("SELECT * FROM animation_bindings ORDER BY character_id,scope,weapon_set,slot,variant")]

        for row in clips:
            row["status"] = self._status(row)
        shared = self.shared_rows()

        manifest_profiles = [
            {
                "characterId": str(row.get("character_id") or ""),
                "skeletonSignature": str(row.get("skeleton_signature") or ""),
            }
            for row in profiles
        ]
        manifest_clips = [
            {
                "id": str(row.get("id") or ""),
                "characterId": str(row.get("character_id") or ""),
                "name": str(row.get("name") or ""),
                "sourcePath": str(row.get("source_path") or ""),
                "preparedPath": str(row.get("prepared_path") or ""),
                "sha256": str(row.get("sha256") or ""),
                "sourceSha256": str(row.get("source_sha256") or ""),
                "assetId": str(row.get("asset_id") or ""),
                "publishedSha256": str(row.get("published_sha256") or ""),
                "moderationState": str(row.get("moderation_state") or ""),
                "revision": int(row.get("revision") or 1),
                "status": str(row.get("status") or ""),
            }
            for row in clips
        ]
        manifest_bindings = [
            {
                "id": str(row.get("id") or ""),
                "characterId": str(row.get("character_id") or ""),
                "scope": str(row.get("scope") or ""),
                "weaponSet": str(row.get("weapon_set") or ""),
                "slot": str(row.get("slot") or ""),
                "variant": int(row.get("variant") or 0),
                "clipId": str(row.get("clip_id") or ""),
                "weight": int(row.get("weight") or 100),
                "looped": bool(row.get("looped")),
                "priority": str(row.get("priority") or "Movement"),
            }
            for row in bindings
        ]
        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "project": PROJECT,
            "weaponSets": list(WEAPON_SETS),
            "profiles": manifest_profiles,
            "clips": manifest_clips,
            "bindings": manifest_bindings,
            "shared": [{"family": r['family'], "scope": r['scope'], "weaponSet": r['weapon_set'],
                        "slot": r['slot'], "variant": r['variant'], "sourceBindingId": r['source_binding_id'],
                        "sourceCharacter": r['source_character'], "assetId": str(r.get('asset_id') or ''),
                        "status": r['status']} for r in shared],
        }
        manifest = self.root / "assets/manifests/character-animations.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        clips_by_id = {str(row["id"]): row for row in clips if str(row.get("asset_id") or "").isdigit() or str(row.get('source_path') or '').endswith('.animation.json')}
        profile_map: dict[str, dict] = {}
        with self.connect() as db:
            family_by_character = {r['id']:r['race'] for r in db.execute('SELECT id,race FROM characters')}
        for profile in profiles:
            profile_map[str(profile["character_id"])] = {
                "skeletonSignature": str(profile.get("skeleton_signature") or ""),
                "family": family_by_character.get(profile['character_id'], ''),
                "base": {},
                "emotions": {},
                "social": {},
                "weapons": {},
            }
        for binding in bindings:
            clip = clips_by_id.get(str(binding["clip_id"]))
            if clip is None:
                continue
            character_id = str(binding["character_id"])
            profile = profile_map.setdefault(character_id, {"skeletonSignature": "", "family": family_by_character.get(character_id,''), "base": {}, "emotions": {}, "social": {}, "weapons": {}})
            descriptor = {
                "clipId": str(clip["id"]),
                "assetId": str(clip["asset_id"]),
                "animationId": "rbxassetid://" + str(clip["asset_id"]),
                "variant": int(binding["variant"]),
                "weight": int(binding["weight"]),
                "looped": bool(binding["looped"]),
                "priority": str(binding["priority"]),
            }
            procedural=str(clip.get('source_path') or '').endswith('.animation.json')
            if procedural:descriptor.update(assetId='',animationId='')
            with self.connect() as documents:
                descriptor['document']=get_document(documents,clip['id'],'procedural' if procedural else (clip.get('published_sha256') or clip['sha256']))
            if str(binding["scope"]) == "base":
                profile["base"].setdefault(str(binding["slot"]), []).append(descriptor)
            elif str(binding['scope']) == 'emotions':
                profile['emotions'].setdefault(str(binding['slot']), []).append(descriptor)
            elif str(binding['scope']) == 'social':
                profile['social'].setdefault(str(binding['slot']), []).append(descriptor)
            else:
                weapon = profile["weapons"].setdefault(str(binding["weapon_set"]), {})
                weapon.setdefault(str(binding["slot"]), []).append(descriptor)

        for profile in profile_map.values():
            for rows in profile["base"].values():
                rows.sort(key=lambda row: row["variant"])
            for rows in profile['emotions'].values():
                rows.sort(key=lambda row: row['variant'])
            for rows in profile['social'].values():
                rows.sort(key=lambda row: row['variant'])
            for weapon in profile["weapons"].values():
                for rows in weapon.values():
                    rows.sort(key=lambda row: row["variant"])

        shared_runtime = {}
        for row in shared:
            if row['status'] != 'PUBLISHED':
                continue
            family_data = shared_runtime.setdefault(row['family'], {'base':{},'social':{},'emotions':{},'weapons':{}})
            with self.connect() as documents:
                document = get_document(documents,row['clip_id'],row.get('published_sha256') or row['sha256'])
            descriptor = dict(clipId=row['clip_id'],assetId=str(row['asset_id']),
                              animationId='rbxassetid://'+str(row['asset_id']),variant=int(row['variant']),
                              weight=int(row['weight']),looped=bool(row['looped']),priority=row['priority'],document=document)
            if row['scope']=='weapon':
                family_data['weapons'].setdefault(row['weapon_set'],{}).setdefault(row['slot'],[]).append(descriptor)
            else:
                family_data[row['scope'] if row['scope']!='base' else 'base'].setdefault(row['slot'],[]).append(descriptor)

        def lua_string(value: str) -> str:
            return json.dumps(str(value), ensure_ascii=False)

        def emit_descriptor(row: dict, indent: str) -> list[str]:
            return [
                indent + "table.freeze({",
                indent + f"\tclipId = {lua_string(row['clipId'])},",
                indent + f"\tassetId = {lua_string(row['assetId'])},",
                indent + f"\tanimationId = {lua_string(row['animationId'])},",
                indent + f"\tvariant = {int(row['variant'])},",
                indent + f"\tweight = {int(row['weight'])},",
                indent + f"\tlooped = {'true' if row['looped'] else 'false'},",
                indent + f"\tpriority = {lua_string(row['priority'])},",
                indent + '\tdocument = '+lua_data(row.get('document'))+',',
                indent + "}),",
            ]

        lines = [
            "-- generated. do not edit by hand.",
            "return table.freeze({",
            f"\tschemaVersion = {SCHEMA_VERSION},",
            '\tproject = "game1",',
            "\tshared = " + lua_data(shared_runtime) + ",",
            "\tprofiles = table.freeze({",
        ]
        for character_id in sorted(profile_map):
            profile = profile_map[character_id]
            lines += [
                f"\t\t[{lua_string(character_id)}] = table.freeze({{",
                f"\t\t\tskeletonSignature = {lua_string(profile['skeletonSignature'])},",
                f"\t\t\tfamily = {lua_string(profile.get('family') or '')},",
                "\t\t\tbase = table.freeze({",
            ]
            for slot in sorted(profile["base"]):
                lines.append(f"\t\t\t\t[{lua_string(slot)}] = table.freeze({{")
                for row in profile["base"][slot]:
                    lines.extend(emit_descriptor(row, "\t\t\t\t\t"))
                lines.append("\t\t\t\t}),")
            lines += ["\t\t\t}),", "\t\t\temotions = table.freeze({"]
            for slot in sorted(profile['emotions']):
                lines.append(f"\t\t\t\t[{lua_string(slot)}] = table.freeze({{")
                for row in profile['emotions'][slot]:lines.extend(emit_descriptor(row, "\t\t\t\t\t"))
                lines.append("\t\t\t\t}),")
            lines += ["\t\t\t}),", "\t\t\tsocial = table.freeze({"]
            for slot in sorted(profile['social']):
                lines.append(f"\t\t\t\t[{lua_string(slot)}] = table.freeze({{")
                for row in profile['social'][slot]: lines.extend(emit_descriptor(row, "\t\t\t\t\t"))
                lines.append("\t\t\t\t}),")
            lines += ["\t\t\t}),", "\t\t\tweapons = table.freeze({"]
            for weapon_set in sorted(profile["weapons"]):
                lines.append(f"\t\t\t\t[{lua_string(weapon_set)}] = table.freeze({{")
                for slot in sorted(profile["weapons"][weapon_set]):
                    lines.append(f"\t\t\t\t\t[{lua_string(slot)}] = table.freeze({{")
                    for row in profile["weapons"][weapon_set][slot]:
                        lines.extend(emit_descriptor(row, "\t\t\t\t\t\t"))
                    lines.append("\t\t\t\t\t}),")
                lines.append("\t\t\t\t}),")
            lines += ["\t\t\t}),", "\t\t}),"]
        lines += ["\t}),", "})", ""]
        target = self.root / "src/shared/character/CharacterAnimationRegistry.luau"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines), encoding="utf-8")
        return payload
