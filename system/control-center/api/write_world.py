"""World, placement and timeline write operations. No HTTP, persistence, or Studio ownership.

Dependencies are supplied by the composition root; unhandled paths return None.
"""
from urllib.parse import unquote
from pathlib import Path

from services.texture_atlas_registry import parse_filename


def route(path, body, deps):
    if not path.startswith(('/api/texture-atlases', '/api/location-assets', '/api/npc-spawns', '/api/monster-spawns', '/api/options', '/api/locations', '/api/timelines',)):
        return None

    def out(status, payload):
        return status, payload

    deco_layouts = deps["deco_layouts"]
    location_assets = deps["location_assets"]
    locations = deps["locations"]
    monster_spawns = deps["monster_spawns"]
    npc_place_spawn = deps["npc_place_spawn"]
    npc_register_spawn = deps["npc_register_spawn"]
    npc_spawns = deps["npc_spawns"]
    options_store = deps["options_store"]
    publication_credentials = deps["publication_credentials"]
    request_active_studio_save = deps["request_active_studio_save"]
    run_timeline_editor_bridge = deps["run_timeline_editor_bridge"]
    sync_monster_to_studio = deps["sync_monster_to_studio"]
    timelines = deps["timelines"]

    if path == "/api/location-assets/studio-sync":
        try:
            payload = body()
            if not isinstance(payload, dict):
                raise ValueError('sync requires a selected Location Asset')
            slug = str(payload.get('slug') or '').strip().lower()
            if not slug:
                raise ValueError('global Location Assets Sync is disabled; select one asset')
            row = location_assets.get(slug)
            if not row:
                raise ValueError('unknown location asset')
            if row.get('status') != 'PUBLISHED':
                raise ValueError('publish this Location Asset before Studio Sync')
            # The M203 independent binding is a direct slug->variant relation.
            # Legacy inherited bindings cannot be acknowledged by a scoped Sync.
            if row.get('atlasBindingSourceSlug') not in (None, '', slug):
                raise ValueError('independent atlas binding required for scoped Studio Sync')
            if not location_assets.atlases.binding('location_asset', slug):
                raise ValueError('direct atlas binding not found')
            revision = row.get('bindingRevision')
            if type(revision) is not int or revision < 1:
                raise ValueError('invalid Location Asset atlas binding revision')
            studio = deps['sync_location_assets_to_studio'](
                slug=slug, binding_revision=revision,
                model_asset_id=str(row.get('model_asset_id') or ''),
                atlas_asset_id=str(row.get('texture_asset_id') or ''))
            # Record changes BEFORE acknowledging a successful atlas binding.
            deps['location_asset_sync_history'].append(
                slug=slug, binding_revision=revision, studio=studio)
            location_assets.atlases.mark_synced('location_asset', slug, revision)
            location_assets.export()
            return out(200, {'studio': studio})
        except Exception as error:
            return out(400, {'error': str(error)})

    if path.startswith('/api/texture-atlases/variants/') and path.endswith('/retire'):
        try:
            raw = path[len('/api/texture-atlases/variants/'):-len('/retire')].strip('/')
            if not raw.isdigit():
                raise ValueError('invalid atlas variant ID')
            payload = body()
            if not isinstance(payload, dict) or type(payload.get('autoClosest', False)) is not bool:
                raise ValueError('invalid atlas retirement request')
            replacement = payload.get('replacementVariantId')
            if replacement is not None and (type(replacement) is not int or replacement < 1):
                raise ValueError('invalid replacement variant ID')
            result = location_assets.atlases.retire_variant(
                int(raw), token=str(payload.get('token') or ''),
                replacement_variant_id=replacement,
                auto_closest=payload.get('autoClosest', False))
            # The SQLite retirement has COMMITTED. An export error must not
            # return a misleading HTTP 400 that encourages repeating deletion.
            # Keep an explicit warning so the operator can reconcile manifests.
            exports = [('location_assets', location_assets.export),
                       ('real_estate', deps['real_estate'].export)]
            if 'character_components' in deps:
                exports.append(('character_components', deps['character_components'].export))
            if 'character_assemblies' in deps:
                exports.append(('characters', deps['character_assemblies'].characters.export))
            warnings = []
            for name, exporter in exports:
                try:
                    exporter()
                except (ValueError, OSError, RuntimeError) as error:
                    warnings.append(f'{name}: {error}')
            result['exportWarnings'] = warnings
            return out(200, result)
        except (ValueError, OSError, RuntimeError) as error:
            return out(400, {'error': str(error)})

    if path == "/api/texture-atlases/variants":
        try:
            return out(200, location_assets.atlases.register_file(str(body().get('sourcePath') or '')))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path.startswith('/api/texture-atlases/variants/') and path.endswith('/republish'):
        try:
            variant_id = int(path[len('/api/texture-atlases/variants/'):-len('/republish')].strip('/'))
            payload = body()
            source_path = str(payload.get('sourcePath') or '')
            previous = location_assets.atlases.get_variant(variant_id)
            if not previous:
                raise ValueError('unknown atlas variant')
            if source_path:
                parsed = parse_filename(Path(source_path).name)
                if not parsed or (parsed['atlasKey'], parsed['width'], parsed['height']) != (
                        previous['atlas_key'], previous['width'], previous['height']):
                    raise ValueError('replacement file must match this atlas name and resolution')
                staged = location_assets.atlases.register_file(source_path)
                if staged['id'] != variant_id:
                    raise ValueError('replacement file must match this atlas name and resolution')
            else:
                staged = location_assets.atlases.get_variant(variant_id)
            # No Open Cloud request for byte-for-byte identical sources.
            if not staged['replacementPending']:
                if not staged['current']:
                    raise ValueError('atlas not yet published; use Publish instead')
                return out(200, {'unchanged': True, 'variant': staged,
                                 'syncedConsumers': 0, 'pendingConsumers': 0})
            credentials = publication_credentials('game1 atlas republish')
            result = location_assets.atlases.ensure_published(variant_id, credentials, 'game1 atlas republish')
            if 'character_components' in deps:
                deps['character_components'].export()
            if 'character_assemblies' in deps:
                deps['character_assemblies'].characters.export()
            # Both domains consume the same publication; export both registries
            # before asking Studio to refresh templates and placed instances.
            location_assets.export()
            deps['real_estate'].export()
            # M216: publishing a SHARED atlas must not silently edit ANY Place.
            # All consumers become pending and must be explicitly synced by slug
            # (Real Estate keeps its own separately targeted Sync operation).
            consumers = location_assets.atlases.consumers(variant_id)
            return out(200, {'variant': result, 'syncedConsumers': 0,
                             'pendingConsumers': len(consumers), 'studioErrors': [],
                             'requiresExplicitStudioSync': True})

        except Exception as error:
            return out(400, {'error': str(error)})

    if path.startswith('/api/texture-atlases/variants/') and path.endswith('/publish'):
        try:
            variant_id = int(path[len('/api/texture-atlases/variants/'):-len('/publish')].strip('/'))
            credentials = publication_credentials('game1 atlas')
            result = location_assets.atlases.ensure_published(variant_id, credentials, 'game1 atlas')
            if 'character_components' in deps:
                deps['character_components'].export()
            if 'character_assemblies' in deps:
                deps['character_assemblies'].characters.export()
            location_assets.export()
            return out(200, result)
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/location-assets":
        try:
            return out(200, location_assets.register(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/location-assets/layout":
        try:
            payload = body()
            result = deco_layouts.save(payload)
            result["studioSave"] = request_active_studio_save()
            return out(200, result)
        except Exception as error:
            return out(400, {"error": str(error)})

    npc_spawn_actions = {
        "/api/npc-spawns/place": lambda body: npc_place_spawn(body),
        "/api/npc-spawns/register": lambda body: npc_register_spawn(body),
        "/api/npc-spawns/select": lambda body: npc_spawns.select(body),
        "/api/npc-spawns/delete": lambda body: npc_spawns.delete(body),
        "/api/npc-spawns/restore": lambda body: npc_spawns.restore(),
        "/api/npc-spawns/validate": lambda body: npc_spawns.validate(),
    }

    if path in npc_spawn_actions:
        try:
            return out(200, npc_spawn_actions[path](body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/monster-spawns/place":
        try:
            return out(200, monster_spawns.place(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/monster-spawns/register":
        try:
            payload = body()
            slug = str(payload.get("monsterSlug") or "").strip().lower()
            sync_monster_to_studio(slug)
            return out(200, monster_spawns.register(payload))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/monster-spawns/select":
        try:
            return out(200, monster_spawns.select(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/monster-spawns/delete":
        try:
            return out(200, monster_spawns.delete(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/monster-spawns/restore":
        try:
            return out(200, monster_spawns.restore())
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/monster-spawns/validate":
        try:
            return out(200, monster_spawns.validate())
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/options":
        try:
            return out(200, options_store.update(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/locations/draw":
        try:
            return out(200, locations.draw(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/locations/register":
        try:
            return out(200, locations.register(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/locations/select":
        try:
            return out(200, locations.select(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/locations/restore":
        try:
            return out(200, locations.restore())
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/locations/delete":
        try:
            return out(200, locations.delete(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/locations/validate":
        try:
            return out(200, locations.validate())
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/timelines/open":
        try:
            payload = body()
            session = timelines.begin_editor_session(str(payload.get("clipId") or ""))
            studio = run_timeline_editor_bridge(session, timelines.event_catalog_for_subject(session["subjectType"]))
            duration = float(studio.get("duration") or 0)
            if duration > 0:
                timelines.update_editor_state({"sessionId": session["sessionId"], "action": "ready", "duration": duration})
            return out(200, {"session": timelines.editor_state(session["sessionId"]), "studio": studio})
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/timelines/editor-event":
        try:
            return out(200, timelines.update_editor_state(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/timelines/save":
        try:
            return out(200, timelines.save(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    location_asset_prefix = "/api/location-assets/"
    if path.startswith(location_asset_prefix) and path.endswith('/atlas-binding'):
        slug = unquote(path[len(location_asset_prefix):-len('/atlas-binding')].strip('/'))
        try:
            payload = body()
            return out(200, location_assets.select_atlas(
                slug, int(payload.get('variantId') or 0),
                int(payload.get('expectedRevision') or 0)))
        except Exception as error:
            return out(400, {"error": str(error)})


    location_asset_publish_suffix = "/publish"

    if path.startswith(location_asset_prefix) and path.endswith(location_asset_publish_suffix):
        slug = unquote(path[len(location_asset_prefix):-len(location_asset_publish_suffix)].strip("/"))
        try:
            payload = body()
            credentials = publication_credentials(str(payload.get("description") or "game1 location asset"))
            scope = str(payload.get('scope') or 'changed')
            force_model = payload.get('forceModel') is True
            return out(200, location_assets.publish(
                slug, credentials, scope=scope, force_model=force_model))
        except Exception as error:
            return out(400, {"error": str(error)})
    return None
