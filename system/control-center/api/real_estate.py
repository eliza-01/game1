"""Real Estate authoring HTTP routes; persistence lives in RealEstateStore."""
from urllib.parse import unquote


def read(parsed, sources):
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
                int(payload.get('expectedRevision', 0)))
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
