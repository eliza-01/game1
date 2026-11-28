# M635 · MNPC Automatic Pose & Assembly Capture

## Контракт

M635: Studio Edit capture из зарегистрированного FULL template и опубликованного idle KeyframeSequence; общий Monster/NPC контракт, weapon mount, точная авторская keyframe около phase 0.35, снимок mesh/texture IDs, rest/posed bone frames и root-relative transforms. Снимок привязан к FULL/equipment/idle fingerprint; атомарная запись, предыдущий снимок сохраняется при ошибке. Не native Animator benchmark, не FBX/UV/bake; Studio NOT_RUN, Runtime FULL. Следующий этап M636 — геометрия, skinning и объединение атласов из снимка.

LOD Manager → MNPC → Capture FULL idle · Studio. Запустить подключённый Studio в Edit, выбрать опубликованный Monster/NPC с базовым looping idle и нажать Capture idle & assembly. Bridge использует существующий command transport, отдельный локальный одноразовый результат с проверкой token/operation. Временный клон шаблона не помещается в Workspace; AI, физика и игровые спавны не запускаются. Используются shared runtime geometry/root/equipment contracts и существующий загрузчик KeyframeSequence. При неподдержанной кривой, неоднозначной иерархии или неполном keyframe захват отклоняется; не заменять pose на T-pose. Точная авторская keyframe, а не интерполированный результат native Animator.

Host сохраняет проверенный JSON в `.control-center/mnpc-lod-capture/{kind}/{slug}.json`. Повторный захват проверяет текущую ревизию, FULL/equipment и idle identity; GET показывает NOT_CAPTURED/STALE/INVALID/CAPTURED. Никаких новых Cloud assets, изменения реестра LOD1 или FBX. Ограничения: 64 mesh, 512 bones, 1200 frames, 200000 poses. Временные экземпляры очищаются. Снимок не содержит треугольники, UV или skin weights; следующий этап должен получить исходную геометрию, сопоставить её со снимком и объединить текстуры без ручного posed FBX. M634 ручной проверяемый authoring остаётся доступен.

## Приёмка

Host/SQLite/bridge тесты и JS double; Studio native execution, геометрия и bake не проверены. A07/T08 открыты. Не заявлять снижение FPS/CPU или production shell-only. Игровой Runtime продолжает FULL, demand pilot OFF по умолчанию.
