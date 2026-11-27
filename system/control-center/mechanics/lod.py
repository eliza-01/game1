"""Client-only Runtime LOD mechanics; no new authoring settings."""
ITEMS = [
    {'id': 'runtime-lod-streaming', 'title': 'Runtime LOD · индекс и очередь',
     'kind': 'Клиентский стриминг', 'scope': 'shared',
     'summary': 'M622: Location incremental assembly, atomic commit и bounded retirement поверх BVH/queue/prototype cache.',
     'sockets': [], 'sections': [
         {'title': 'Location Assets', 'lines': [
             'StaticPlacementIndex строится один раз по manifest: 3D-границы влияния hide + hysteresis каждой записи. Policy.Resolve остаётся единственным источником FULL / LOD1 / LOD2 / UNLOADED.',
             'При телепортации обрабатываются новая область и прежние desired/actual, пока старые визуалы не выгружены. Невидимые записи вне области логически UNLOADED; первый sample сохраняет nil для локальных записей.',
             'Пороговый кэш учитывает запас до ±h и смещение от последнего resolve. При неподвижной камере стабильные дистанции и BVH не пересчитываются. Очередь хранит одну заявку на placement, отменяет устаревшие, приоритет — выгрузка, затем aging и дистанция; равные дистанции — порядок manifest. Интервал resolve 0,25 с и fallback сохранены; Runtime Location jobs выполняются на существующем Heartbeat каждый кадр.',
             'LodPrototypeCache keyed by template Instance, generation, variant and FULL component contract. Missing/incomplete/ready/invalid states are event-invalidated; late folder/Ready/children and attributes recover without camera movement. Incomplete cases retry twice; missing templates stop polling after Ready=true. Frozen metadata caches counts, source MeshParts, relative transforms, published pivot/bounds and FULL component-name map. Assembly and composite preparation reuse it; stale generation forces an atomic visual replacement.',
             'M622: одна активная сборка до 64 meshes вне Workspace; target bounds, clone, transform/appearance, parent и weld учитываются отдельными группами работы. 12 build / 8 cleanup units на кадр; отдельный atomic commit до 132 units для 64 proxy links; не более двух retired bundles. Старый visual остаётся до commit, устаревшие jobs отменяются, cleanup порционный.',
         ]},
         {'title': 'Real Estate / Composite', 'lines': [
             'Дома пока сохраняют отдельный HouseVisualAdapter и дистанции до bounds каждой части. LOD1 prototype readiness shares cache and stale-generation replacement; spatial index / transition queue / общий budget houses remain stage 5; текущий отдельный резерв 8 на observation tick. Сокеты, цвета, замки, лифты, физика и server proxy не меняются.',
             'Для составных объектов сохраняется отдельный проход эффектов по actual, включая позднюю репликацию технического root. Серверная навигация не зависит от клиентского LOD.',
         ]},
         {'title': 'Недостающее / проверить', 'lines': [
             'Runtime Location incremental assembly реализован. Studio Preview multipart использует тот же job builder синхронно; House integration, budgeted Preview scheduling, event-driven effect invalidation и runtime profiling остаются открыты. Clone/Destroy/Parent и commit неделимы внутри группы; CPU deadline не гарантируется. Aging после 8 ticks; root/proxy absence retryable.',
             'Studio / Runtime / DEV Mobile, две камеры с разным LOD, коллизии, телепортация, CPU и память требуют фактической приёмки. Канбан KBN-0037 остаётся IN_PROGRESS.',
         ]},
     ], 'sources': ['location-streamer', 'static-placement-index', 'location-lod-candidates',
                    'lod-threshold-cache', 'lod-transition-queue', 'lod-prototype-cache',
                    'location-lod-assembly', 'lod-assembly-job', 'lod-runtime-work', 'location-lod-policy', 'house-visual-adapter',
                    'location-composite-visual', 'runtime-lod-spec']},
]
