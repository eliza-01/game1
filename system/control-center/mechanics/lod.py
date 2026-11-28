"""Client-only Runtime LOD mechanics; no new authoring settings."""
ITEMS = [
    {'id': 'runtime-lod-streaming', 'title': 'Runtime LOD · индекс и очередь',
     'kind': 'Клиентский стриминг', 'scope': 'shared',
     'summary': 'M626: near-first Runtime LOD, общий бюджет и событийные эффекты.',
     'sockets': [], 'sections': [
         {'title': 'Location Assets', 'lines': [
             'StaticPlacementIndex строится один раз по manifest: 3D-границы влияния hide + hysteresis каждой записи. Policy.Resolve остаётся единственным источником FULL / LOD1 / LOD2 / UNLOADED.',
             'При телепортации обрабатываются новая область и прежние desired/actual, пока старые визуалы не выгружены. Невидимые записи вне области логически UNLOADED; первый sample сохраняет nil для локальных записей.',
             'Пороговый кэш учитывает запас до ±h и смещение от последнего resolve. При неподвижной камере стабильные дистанции и BVH не пересчитываются. Очередь хранит одну заявку на placement, отменяет устаревшие, приоритет — независимая выгрузка, кольцо 32 studs от персонажа, cold перед upgrade, aging внутри кольца/класса; равные дистанции — порядок manifest. Интервал resolve 0,25 с и fallback сохранены; Runtime Location jobs выполняются на существующем Heartbeat каждый кадр.',
             'LodPrototypeCache keyed by template Instance, generation, variant and FULL component contract. Missing/incomplete/ready/invalid states are event-invalidated; late folder/Ready/children and attributes recover without camera movement. Incomplete cases retry twice; missing templates stop polling after Ready=true. Frozen metadata caches counts, source MeshParts, relative transforms, published pivot/bounds and FULL component-name map. Assembly and composite preparation reuse it; stale generation forces an atomic visual replacement.',
             'M626: LodLoadPriority по поверхности authored bounds, не по pivot. Камера по-прежнему определяет desired; персонаж — порядок загрузки. Ближайшее кольцо gate даже при missing template/proxy, 4 s без actual progress разрешают следующие кольца. Четыре async FULL slots сохранены; ready far result может уступить слот ближнему, in-flight не отменяется. Native GPU/CDN/replication order не гарантируется.',
             'M622: одна активная сборка до 64 meshes вне Workspace; target bounds, clone, transform/appearance, parent и weld учитываются отдельными группами работы. 12 build / 8 cleanup units на кадр; отдельный atomic commit до 132 units для 64 proxy links; не более двух retired bundles. Старый visual остаётся до commit, устаревшие jobs отменяются, cleanup порционный.',
         ]},
         {'title': 'Real Estate / Composite', 'lines': [
             'M623: каждая часть дома — самостоятельная запись общего BVH/queue/work budget. Surface distance до scaled bounds, без LOD1 — FULL до собственного hide. FULL async: четыре in-flight/ready слота, retry 15 сек, generation/proxy guard, detached job и atomic commit. При пропаже proxy движущийся visual отсоединяется и снимается DoorRaycast binding; при возврате proxy обновляются CFrame и цвет. FollowMoving обходит только активные движущиеся части.',
             'M625: эффекты составных объектов реагируют на actual commit/detach и появление root/descendants по compiled path. Общие префиксы пути подписаны один раз; глобального периодического обхода больше нет. Сохранение Enabled, поздний stream-in и Stop restore; отдельный authoritative state для динамического выключения скрытых эффектов не добавлен. Серверная навигация не зависит от клиентского LOD.',
         ]},
         {'title': 'Диагностика M624', 'lines': [
             'DEV debug dock → LOD diagnostics → Start capture / Stop capture. По умолчанию выключена; один существующий Heartbeat, без remotes. Heartbeat/callback elapsed, queue/desired latency, cache/async/work counters, peaks, client memory; не CPU всего клиента.',
             'Отчёт локальный, читается на PC и телефоне; JSON в client Output. Studio Preview teardown освобождает connections и возвращает FULL, сборка preview остаётся синхронной.',
         ]},
         {'title': 'MNPC · следующий этап (план, не реализовано)', 'lines': [
             'FULL / LOD1 / UNLOADED; один статический mesh на визуальный вариант, без клиентского visual Animator/скелета и sampler начиная с LOD1; движение/поворот сохраняются. Сначала доказать отделение authoritative Bone pose от клиентского rig. AI и боевой hitbox не зависят от наблюдателя. См. ТЗ MNPC.',
             'Socket & Door Optimization отложена до новой системы взаимодействий с выбором этажа. Нагрузочная приёмка и incremental Studio Preview отложены владельцем.',
         ]},
         {'title': 'Недостающее / проверить', 'lines': [
             'Runtime Location incremental assembly реализован. Studio Preview multipart использует тот же job builder синхронно; House integration реализована; event-driven effects реализованы; budgeted Preview scheduling отложен владельцем; runtime profiling открыт. Clone/Destroy/Parent и commit неделимы внутри группы; CPU deadline не гарантируется. Stale raw async MeshPart удаляется сразу (до четырёх слотов), вне счётчика job. Aging после 8 ticks внутри кольца и класса; root/proxy absence retryable.',
             'Studio / Runtime / DEV Mobile, две камеры с разным LOD, коллизии, телепортация, CPU и память требуют фактической приёмки. Нагрузочная приёмка отложена владельцем; функциональная загрузка M626 принята владельцем, формальная матрица открыта. Канбан KBN-0037 остаётся IN_PROGRESS.',
         ]},
     ], 'sources': ['location-streamer', 'static-placement-index', 'location-lod-candidates',
                    'lod-threshold-cache', 'lod-transition-queue', 'lod-load-priority', 'lod-prototype-cache',
                    'location-lod-assembly', 'lod-assembly-job', 'lod-runtime-work', 'location-lod-policy', 'house-visual-adapter',
                    'house-mesh-requests', 'location-composite-visual', 'location-composite-effects', 'runtime-lod-spec', 'lod-diagnostics', 'lod-debug-controller', 'lod-acceptance', 'mnpc-lod-spec']},
]
