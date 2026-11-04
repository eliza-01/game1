"""Real Estate authoring HTTP routes; persistence lives in RealEstateStore."""
from urllib.parse import unquote


def read(parsed, sources):
    if parsed.path == '/api/real-estate/placements':
        return 200, sources['real_estate_placements'].snapshot()
    if parsed.path == '/api/real-estate':
        try:
            snapshot = sources['real_estate'].snapshot()
            snapshot['publication'] = sources['publication_config']()
            return 200, snapshot
        except (ValueError, OSError) as error:
            return 400, {'error': str(error)}
    if parsed.path.startswith('/api/real-estate/') and parsed.path.endswith('/publication-job'):
        slug = unquote(parsed.path[len('/api/real-estate/'):-len('/publication-job')].strip('/'))
        return 200, {'job': sources['real_estate_publications'].get(slug)}
    if parsed.path.startswith('/api/real-estate/') and parsed.path.endswith('/publications'):
        slug = unquote(parsed.path[len('/api/real-estate/'):-len('/publications')].strip('/'))
        return 200, {'items': sources['real_estate'].publications(slug)}
    return None


def write(path, body, deps):
    if not path.startswith('/api/real-estate'):
        return None
    store = deps['real_estate']
    try:
        if path == '/api/real-estate/placements/bind':
            payload = body()
            slug = str(payload.get('houseSlug') or '').strip()
            plot = payload.get('plotIndex')
            if type(plot) is not int or not 1 <= plot <= 50:
                raise ValueError('plot must be between 1 and 50')
            if store.get(slug) is None:
                raise ValueError('choose a registered house')
            # Studio owns the measured transform; browser data never supplies a CFrame.
            capture = deps['capture_house_placement'](slug, plot)
            return 200, {'item': deps['real_estate_placements'].bind(slug, plot, capture)}
        if path == '/api/real-estate/placements/preview':
            payload = body()
            slug = str(payload.get('houseSlug') or '').strip()
            plot = payload.get('plotIndex')
            action = payload.get('action')
            if type(plot) is not int or not 1 <= plot <= 50 or action not in ('place', 'clear'):
                raise ValueError('choose a plot and a Place/Clear action')
            if not store.get(slug):
                raise ValueError('unknown registered house')
            binding = deps['real_estate_placements'].get(slug, plot)
            if action == 'place' and binding is None:
                raise ValueError('Bind this house and plot before Place')
            studio = deps['preview_house_placement'](slug, plot, action, binding)
            return 200, {'studio': studio}
        if path == '/api/real-estate/placements/bulk':
            payload = body()
            if not isinstance(payload, dict):
                raise ValueError('invalid bulk placement request')
            action = payload.get('action')
            if action == 'place_all':
                slug = payload.get('houseSlug')
                if type(slug) is not str or not store.get(slug):
                    raise ValueError('select a registered house for Place all')
                # The browser selects only the house. Transforms and anchoring
                # always come from saved authoring bindings, never from HTTP.
                bindings = [item for item in deps['real_estate_placements'].snapshot()['items']
                            if item['houseSlug'] == slug]
                if not bindings:
                    raise ValueError('no saved Placement bindings for this house')
                studio = deps['bulk_house_placements'](slug, action, bindings)
            elif action == 'clear_all':
                # Clears managed authored previews only, including orphaned
                # previews whose binding was deleted after placement.
                studio = deps['bulk_house_placements'](None, action)
            else:
                raise ValueError('unknown Place all / Clear all action')
            return 200, {'studio': studio}
        if path == '/api/real-estate/placements/anchors':
            payload = body()
            if not isinstance(payload, dict) or type(payload.get('anchored')) is not bool:
                raise ValueError('anchored must be a boolean')
            scope = payload.get('scope')
            placements = deps['real_estate_placements']
            if scope == 'all':
                targets = [{'houseSlug': x['houseSlug'], 'plotIndex': x['plotIndex']}
                           for x in placements.snapshot()['items']]
            elif scope == 'one':
                slug, plot = payload.get('houseSlug'), payload.get('plotIndex')
                if type(slug) is not str or type(plot) is not int or not placements.get(slug, plot):
                    raise ValueError('choose an existing house-to-plot binding')
                targets = [{'houseSlug': slug, 'plotIndex': plot}]
            else:
                raise ValueError('choose one or all placement bindings')
            # Studio first, database second: a bridge failure does not silently
            # claim a state that was never applied in Studio.
            if not targets:
                return 200, {'changed': 0, 'studio': {'status': 'no_bindings'}}
            studio = deps['anchor_house_placements'](targets, payload['anchored'])
            changed = placements.set_anchored(targets, payload['anchored'])
            return 200, {'changed': changed, 'studio': studio}
        if path.startswith('/api/real-estate/') and path.endswith('/mesh-inspect'):
            slug = unquote(path[len('/api/real-estate/'):-len('/mesh-inspect')].strip('/'))
            payload = body()
            return 200, store.inspect_mesh(slug, str(payload.get('part') or ''), str(payload.get('sourcePath') or ''))
        if path.startswith('/api/real-estate/') and path.endswith('/mesh-source'):
            slug = unquote(path[len('/api/real-estate/'):-len('/mesh-source')].strip('/'))
            payload = body()
            updated = store.replace_mesh(slug, str(payload.get('part') or ''),
                str(payload.get('sourcePath') or ''), expected_revision=int(payload.get('expectedRevision', 0)))
            return 200, updated
        if path == '/api/real-estate/inspect':
            return 200, store.inspect(str(body().get('sourcePath') or ''))
        if path == '/api/real-estate':
            payload = body()
            previous = store.get(str(payload.get('existingSlug') or '')) if payload.get('existingSlug') else None
            updated = store.register(payload)
            if (previous and previous.get('meshOptions') != updated.get('meshOptions')
                    and updated['status'] == 'PUBLISHED'):
                try:
                    deps['sync_real_estate_to_studio'](updated['slug'])
                    updated['studioSyncStatus'] = 'synced'
                except (RuntimeError, ValueError, OSError, KeyError) as exc:
                    updated['studioSyncStatus'] = 'pending_studio_sync'
                    updated['studioError'] = str(exc)
            return 200, updated
        if path.startswith('/api/real-estate/') and path.endswith('/atlas-binding'):
            # A saved binding is authoritative even if Studio is offline.
            # Sync failures remain visible and retryable, never rolled back
            # into a different published ID.
            slug = unquote(path[len('/api/real-estate/'):-len('/atlas-binding')].strip('/'))
            payload = body()
            part = str(payload.get('part') or '').strip()
            updated = store.select_atlas(slug, part, int(payload['variantId']),
                int(payload.get('expectedRevision', 0)), mode=str(payload.get('mode') or 'variant'))
            try:
                studio = deps['sync_real_estate_to_studio'](slug)
                return 200, {'item': updated, 'studio': studio['studio'], 'studioSyncStatus': 'synced'}
            except (RuntimeError, ValueError, OSError, KeyError) as exc:
                return 200, {'item': updated, 'studioSyncStatus': 'pending_studio_sync',
                    'studioError': str(exc)}
        if path.startswith('/api/real-estate/') and path.endswith('/sync'):
            slug = unquote(path[len('/api/real-estate/'):-len('/sync')].strip('/'))
            part = str(body().get('part') or '').strip()
            return 200, deps['sync_real_estate_to_studio'](slug, part=part or None)
        if path.startswith('/api/real-estate/') and path.endswith('/publish-async'):
            slug = unquote(path[len('/api/real-estate/'):-len('/publish-async')].strip('/'))
            payload = body()
            credentials = deps['publication_credentials'](str(payload.get('description') or ''))
            job = deps['real_estate_publications'].start(slug, credentials,
                scope=str(payload.get('scope') or 'all'))
            return 202, {'job': job}
        if path.startswith('/api/real-estate/') and path.endswith('/publish'):
            slug = unquote(path[len('/api/real-estate/'):-len('/publish')].strip('/'))
            payload = body()
            credentials = deps['publication_credentials'](str(payload.get('description') or ''))
            return 200, store.publish(slug, credentials, scope=str(payload.get('scope') or 'all'))
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        return 400, {'error': str(error)}
    return None
