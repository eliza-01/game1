"""Client-only Runtime LOD mechanics; no new authoring settings."""
ITEMS = [
    {'id': 'runtime-lod-streaming', 'title': 'Runtime LOD · индекс и очередь',
     'kind': 'Клиентский стриминг', 'scope': 'shared',
     'summary': 'M621: BVH, threshold queue и event-driven prototype readiness cache с immutable geometry metadata.',
     'sockets': [], 'sections': [
         {'title': 'Location Assets', 'lines': [
             'StaticPlacementIndex строится один раз по manifest: 3D-границы влияния hide + hysteresis каждой записи. Policy.Resolve остаётся единственным источником FULL / LOD1 / LOD2 / UNLOADED.',
             'При телепортации обрабатываются новая область и прежние desired/actual, пока старые визуалы не выгружены. Невидимые записи вне области логически UNLOADED; первый sample сохраняет nil для локальных записей.',
             'Пороговый кэш учитывает запас до ±h и смещение от последнего resolve. При неподвижной камере стабильные дистанции и BVH не пересчитываются. Очередь хранит одну заявку на placement, отменяет устаревшие, приоритет — выгрузка, затем aging и дистанция; равные дистанции — порядок manifest. Интервал 0,25 с, fallback, бюджет 8 и Studio Preview сохранены.',
             'LodPrototypeCache keyed by template Instance, generation, variant and FULL component contract. Missing/incomplete/ready/invalid states are event-invalidated; late folder/Ready/children and attributes recover without camera movement. Incomplete cases retry twice; missing templates stop polling after Ready=true. Frozen metadata caches counts, source MeshParts, relative transforms, published pivot/bounds and FULL component-name map. Assembly and composite creation reuse it; stale generation forces an atomic visual replacement.',
         ]},
         {'title': 'Real Estate / Composite', 'lines': [
             'Дома пока сохраняют отдельный HouseVisualAdapter и дистанции до bounds каждой части. LOD1 prototype readiness shares cache and stale-generation replacement; spatial index / transition queue / budget houses remain future stage. Сокеты, цвета, замки, лифты, физика и server proxy не меняются.',
             'Для составных объектов сохраняется отдельный проход эффектов по actual, включая позднюю репликацию технического root. Серверная навигация не зависит от клиентского LOD.',
         ]},
         {'title': 'Недостающее / проверить', 'lines': [
             'Порционная сборка и реальный work budget, common House index/queue, event-driven effect invalidation и runtime profiling — следующие этапы. Prototype structural readiness больше не пересчитывается в steady state; incomplete status использует bounded retries, root/proxy absence остаётся retryable transition. Aging после 8 ticks; на чётных ticks тяжёлая просроченная Location-заявка может использовать полный бюджет; нечётные ticks сохраняют резерв домов.',
             'Studio / Runtime / DEV Mobile, две камеры с разным LOD, коллизии, телепортация, CPU и память требуют фактической приёмки. Канбан KBN-0037 остаётся IN_PROGRESS.',
         ]},
     ], 'sources': ['location-streamer', 'static-placement-index', 'location-lod-candidates',
                    'lod-threshold-cache', 'lod-transition-queue', 'lod-prototype-cache',
                    'location-lod-assembly', 'location-lod-policy', 'house-visual-adapter',
                    'location-composite-visual', 'runtime-lod-spec']},
]
