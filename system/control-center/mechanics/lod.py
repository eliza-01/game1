"""Client-only Runtime LOD mechanics; no new authoring settings."""
ITEMS = [
    {'id': 'runtime-lod-streaming', 'title': 'Runtime LOD · индекс и очередь',
     'kind': 'Клиентский стриминг', 'scope': 'shared',
     'summary': 'M620: пространственный индекс, пороговый кэш и очередь переходов.',
     'sockets': [], 'sections': [
         {'title': 'Location Assets', 'lines': [
             'StaticPlacementIndex строится один раз по manifest: 3D-границы влияния hide + hysteresis каждой записи. Policy.Resolve остаётся единственным источником FULL / LOD1 / LOD2 / UNLOADED.',
             'При телепортации обрабатываются новая область и прежние desired/actual, пока старые визуалы не выгружены. Невидимые записи вне области логически UNLOADED; первый sample сохраняет nil для локальных записей.',
             'Пороговый кэш учитывает запас до ±h и смещение от последнего resolve. При неподвижной камере стабильные дистанции и BVH не пересчитываются. Очередь хранит одну заявку на placement, отменяет устаревшие, приоритет — выгрузка, затем aging и дистанция; равные дистанции — порядок manifest. Интервал 0,25 с, fallback, бюджет 8 и Studio Preview сохранены.',
         ]},
         {'title': 'Real Estate / Composite', 'lines': [
             'Дома пока сохраняют отдельный HouseVisualAdapter и дистанции до bounds каждой части. Сокеты, цвета, замки, лифты, физика и server proxy не меняются.',
             'Для составных объектов сохраняется отдельный проход эффектов по actual, включая позднюю репликацию технического root. Серверная навигация не зависит от клиентского LOD.',
         ]},
         {'title': 'Недостающее / проверить', 'lines': [
             'Кэш готовности прототипов, порционная сборка, индекс частей домов и событийные эффекты — следующие этапы. Пока fallback/proxy проверяются каждые 0,25 с даже при неподвижной камере. Aging после 8 ticks; на чётных ticks тяжёлая просроченная Location-заявка может использовать полный бюджет; нечётные ticks сохраняют резерв домов.',
             'Studio / Runtime / DEV Mobile, две камеры с разным LOD, коллизии, телепортация, CPU и память требуют фактической приёмки. Канбан KBN-0037 остаётся IN_PROGRESS.',
         ]},
     ], 'sources': ['location-streamer', 'static-placement-index', 'location-lod-candidates',
                    'lod-threshold-cache', 'lod-transition-queue', 'location-lod-policy', 'house-visual-adapter', 'location-composite-visual', 'runtime-lod-spec']},
]
