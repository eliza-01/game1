# M398 · Location Physics Sync и LandscapePainter Runtime

**Статус:** код и офлайн-XML тесты; Studio Play и мобильный DEV пока не подтверждены. База: дамп 20.11.2026, 19:35:55.

- Последний Scan #189: все 4 `christmas_tree_01` имеют `needsRig=false`. Новая опубликованная модель не требует исключения для старого `col_mesh`. Специальное принятие отсутствующего физического MeshPart у *скелетных* моделей удалено; исторические публикации Roblox неизменяемы.
- `LocationNeedsPhysics` сравнивает `CanCollide`, `CanQuery`, `CanTouch`, `DoubleSided`, `CollisionFidelity` с зарегистрированными настройками. Place Registry теперь предлагает Sync и для обычных DecoManager-размещений. Он применяет те же правила `MeshPhysicsCore`, с Undo и rollback.
- В Studio Scan подтверждённые LandscapePainter attachments получают **только read-only Runtime evidence** (полная иерархия, pivot, проверенный авторский root). Владение остаётся LandscapePainter, отдельного Placement ID нет. Неактуальный/сломанный подвес в Runtime не допускается.
- Общий `location_runtime_build.py` валидирует exact XML и превращает только идентифицированные видимые MeshPart в технические `Part` (без изменения referent). Скелеты, Weld, Attachment, Fire, Light, ParticleEmitter, существующая физика и подвес остаются авторскими. Отдельный стример не создаётся.
- Клиентский `LocationWorldStreamer` управляет как FULL-мешами, так и локальной видимостью `Light/Fire/Smoke/Sparkles/ParticleEmitter/Beam/Trail` при загрузке/выгрузке, не меняя серверные объекты. Динамические изменения `Enabled` во время скрытия эффектов и скелетное деформирование требуют Studio/DEV проверки. Sound/скрипты/серверные ограничения не переносятся.
- В проектный Streaming Profile включены `christmas_tree_01`, `lantern_02`, `lantern_03`, `ground_torch_01`. Preflight остаётся **fail-closed** до нового Sync/Scan, публикации без COL-мешей и подтверждённого сохранённого `.rbxlx`.
- `wooden_bar_01` не включён автоматически: 50 текущих MeshPart используют `CanCollide=true` с `PreciseConvexDecomposition`. Замена их физики на Part-бокс без нового Collision Blueprint изменила бы игровую геометрию; требуется отдельное авторское решение, а не невидимое изменение коллизии.

## Критерии Studio

1. Обновить плагин. Place Registry: Sync физики `lantern_02`, затем новый Scan.
2. Разрешить проблемы публикации `ground_torch_01` (в текущей опубликованной версии содержится лишний не-визуальный MeshPart) и `campfire_01`, если он тоже будет включён. Из-за защиты принадлежности/геометрии это не лечится случайным Repair.
3. Сохранить новый авторский XML Place. LOD Manager → Preflight → backup → Runtime Draft.
4. Проверить полный список ассетов и составных моделей, огонь и свет на сменах дистанции (в том числе после выгрузки Roblox Native Streaming), а также сохранность кликабельных частей, подвесов, физики и анимаций. Флаг `publishAllowed=false` намеренно остаётся закрытым.
