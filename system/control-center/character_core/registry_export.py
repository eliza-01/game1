"""Character runtime selection and reproducible JSON/Luau registry projections."""
from __future__ import annotations


import json
from character_core.archetype_contract import SCHEMA_VERSION, PROJECT, RACES, GENDERS, DEFAULT_STATS

class CharacterRegistryExportMixin:
    def runtime_selection(self):
        default_id = self.active_id()
        admin_id = self.admin_id()
        default = self.get(default_id) if default_id else None
        admin = self.get(admin_id) if admin_id else None
        return dict(mode='assembled' if default and default.get('assembly_resolved', {}).get('ready') else 'unconfigured',
                    defaultArchetypeId=default_id, studioAdminArchetypeId=admin_id,
                    defaultReady=bool(default and default.get('assembly_resolved', {}).get('ready')),
                    adminReady=bool(admin and admin.get('assembly_resolved', {}).get('ready')),
                    reason='' if default else 'register and set a default character assembly')

    def snapshot(self):
        return {
            "schemaVersion": SCHEMA_VERSION,
            "items": self.list(),
            "activeArchetypeId": self.active_id(),
            "defaultArchetypeId": self.active_id(),
            "studioAdminArchetypeId": self.admin_id(),
            "runtime": self.runtime_selection(),
            "options": self.options(),
        }

    def export(self):
        rows = []
        for row in self.list():
            try:
                analysis = json.loads(str(row.get("skeleton_json") or "{}"))
            except Exception:
                analysis = {}
            rows.append(
                {
                    "id": row["id"],
                    "displayName": row["display_name"],
                    "race": row.get("race") or "",
                    "gender": row.get("gender") or "",
                    "status": self._status(row),
                    "revision": row["revision"],
                    "visualMode": row.get('visual_mode') or 'model',
                    "assembly": row.get('assembly_resolved'),
                    "stats": row.get("stats") or dict(DEFAULT_STATS),
                    "model": {
                        "sourcePath": row["source_path"],
                        "preparedPath": row["prepared_path"],
                        "sha256": row["sha256"],
                        "assetId": row["model_asset_id"],
                        "replacementPending": bool(int(row.get("model_replacement_pending") or 0)),
                        "publishedSha256": row.get("published_sha256") or "",
                        "publicationPipeline": row.get("publication_pipeline") or "",
                        "moderationState": row.get("moderation_state") or "",
                    },
                    "skeleton": {
                        "armature": row.get("armature_name") or "",
                        "boneCount": int(row.get("bone_count") or 0),
                        "meshCount": int(row.get("mesh_count") or 0),
                        "signature": row.get("skeleton_signature") or "",
                        "structureSignature": row.get("skeleton_structure_signature") or "",
                        "bones": analysis.get("bones") or [],
                    },
                }
            )

        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "project": PROJECT,
            "racePool": list(RACES),
            "genderPool": list(GENDERS),
            "activeArchetypeId": self.active_id(),
            "defaultArchetypeId": self.active_id(),
            "studioAdminArchetypeId": self.admin_id(),
            "archetypes": rows,
        }
        manifest = self.root / "assets/manifests/character-archetypes.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        def lua(value):
            if value is None:
                return "nil"
            if isinstance(value, bool):
                return "true" if value else "false"
            if isinstance(value, (int, float)):
                return str(value)
            return json.dumps(str(value), ensure_ascii=False)

        lines = [
            "-- generated. do not edit by hand.",
            "return table.freeze({",
            f"\tschemaVersion = {SCHEMA_VERSION},",
            '\tproject = "game1",',
            f"\tactiveArchetypeId = {lua(self.active_id())},",
            f"\tdefaultArchetypeId = {lua(self.active_id())},",
            f"\tstudioAdminArchetypeId = {lua(self.admin_id())},",
            "\tarchetypes = {",
        ]
        for row in rows:
            model = row["model"]
            skeleton = row["skeleton"]
            lines += [
                "\t\ttable.freeze({",
                f'\t\t\tid = {lua(row["id"])},',
                f'\t\t\tdisplayName = {lua(row["displayName"])},',
                f'\t\t\trace = {lua(row["race"])},',
                f'\t\t\tgender = {lua(row["gender"])},',
                f'\t\t\tstatus = {lua(row["status"])},',
                f'\t\t\tvisualMode = {lua(row["visualMode"])},',
                f'\t\t\trevision = {row["revision"]},',
                "\t\t\tstats = table.freeze({",
                *[f'\t\t\t\t{key} = {lua(value)},' for key, value in row["stats"].items()],
                "\t\t\t}),",
                "\t\t\tmodel = table.freeze({",
                f'\t\t\t\tassetId = {lua(model["assetId"])},',
                f'\t\t\t\tsourcePath = {lua(model["sourcePath"])},',
                f'\t\t\t\tsha256 = {lua(model["sha256"])},',
                "\t\t\t}),",
                "\t\t\tskeleton = table.freeze({",
                f'\t\t\t\tarmature = {lua(skeleton["armature"])},',
                f'\t\t\t\tboneCount = {skeleton["boneCount"]},',
                f'\t\t\t\tmeshCount = {skeleton["meshCount"]},',
                f'\t\t\t\tsignature = {lua(skeleton["signature"])},',
                "\t\t\t}),",
                "\t\t}),",
            ]
            if row.get('assembly'):
                from character_core.assemblies import lua_table
                lines.insert(len(lines)-1, '\t\t\tassembly = '+lua_table(row['assembly'])+',')
        lines += ["\t},", "})", ""]
        (self.root / "src/shared/character").mkdir(parents=True, exist_ok=True)
        (self.root / "src/shared/character/CharacterRegistry.luau").write_text("\n".join(lines), encoding="utf-8")
        return payload
