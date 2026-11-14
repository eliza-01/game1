# M343A — Location Assets Collision Blueprint (подготовительный патч)

**База:** M342T (Game1Bridge уже исправлен). **Изменения:** новый формат данных / API / Kanban. **Нет изменений:** Roblox Studio, Place, Studio Bridge, Rojo, Real Estate, Atlas Registry, опубликованные Asset ID.

## Что делает патч

- Создаёт при инициализации LocationAssetStore новую пустую таблицу `location_asset_collision_blueprints`; существующие таблицы и значения COL/Atlas не изменяются.
- Сохраняет до 256 стандартных Roblox Parts на Location Asset, с проверками `shape`, `size`, `CFrame` и `CollisionGroup`.
- Поддерживает историю ревизий, optimistic concurrency, idempotent повторную запись, чтение/сводку, перенос при rename и архивирование при retire.
- Готовит основу для будущих Studio Capture / Preview и генерации серверных коллизий.

## API (пока для автоматизации, не UI)

`GET /api/location-assets/{slug}/collision-blueprint` -> `{revision:0,blueprint:null}` или последняя ревизия.

`POST /api/location-assets/{slug}/collision-blueprint` -> `{expectedRevision:0,blueprint:{schemaVersion:1,pivot:"Model:GetPivot()",parts:[...]}}`.

Это авторизованные Control Center API; команда сама не создаёт Part в Studio. Пользовательская кнопка Capture появится отдельным патчем после внедрения Studio Bridge transport. **Не вводите JSON вручную вместо штатного Capture в реальном проекте.**

## Почему это отдельный шаг

Недавняя регрессия Game1Bridge из-за синтаксической ошибки в другом модуле показала, что миграцию данных и Studio-транспорт следует разделять. Здесь работоспособность существующих Plots/Place Registry не зависит от новой функции.

## Оставшиеся этапы

- M343B: выбор/захват и просмотр набора Parts непосредственно в Studio; сохранение относительно `Model:GetPivot()`.
- M343C: независимая установка/очистка Physics Parts на существующих Location placements, Undo, история Sync; никаких изменений геометрии и pivot.
- M343D: `Atlas | Roblox Material + Color` в регистрации/публикации, работа без Image ID, полная двусторонняя Studio Sync с очисткой TextureID/ColorMap и изменением Material/Color.

**Не нужно** переустанавливать Studio-плагин или Rojo после M343A. Control Center Host Agent нужно перезапустить, чтобы Python-эндпоинты стали доступны. Коммит и резервная копия SQLite перед первым запуском новой версии рекомендуются.

## Smoke test

1. `python system/verify/verify.py`
2. `python -m unittest discover -s system/verify -p "test_location_collision_blueprint_m343.py" -v`
3. `python -m unittest discover -s system/verify -p "test_development_kanban_m339.py" -q`
4. Перезапустить Control Center, открыть Development Kanban: появилась `KBN-0014`.
5. Убедиться, что Real Estate, Plots, Place Registry и видимые Location Assets остались без изменения.

Старые M162 legacy texture inheritance тесты остаются с 6 ошибками на исходной M342T и M343A — они не подтверждают регрессию данного патча.
