# M199 — Shared Asset retirement · Real Estate + Location Assets

База: `game1_diag_2026-11-02_22-17-52.zip` + M198. **Удаление регистрации модели не является удалением опубликованного Roblox Image Asset**.

## Проблема

До M199 `RealEstateStore.delete()` отклонял удаление `house_level4_01`, если `house_level5_01 / door` хранил `reuseReference=estate:house_level4_01:house`. `LocationAssetStore.delete()` аналогично блокировал владельца, указанного в `texture_reference_slug` других Location Assets. Старое сообщение просило вручную заменить зависимую текстуру, хотя исходный опубликованный Image Asset ID должен сохраняться.

## Новый контракт

1. `GET /api/asset-retirement/impact?kind=estate|location&slug=<slug>` — строго read-only. Отдаёт граф прямых и транзитивных потребителей, связанные части, порядок удаления и SHA-256 `token` состояния. Данные не изменяет.
2. `POST /api/asset-retirement/execute` — `{kind,slug,mode,token}`. `mode=preserve` по умолчанию: удаляет только выбранную регистрацию. Зависимые модели и их источники остаются; исходные идентификаторы общих текстур разрешаются через `retained_shared_textures`.
3. `mode=all` — явное удаление всех перечисленных зависимых **регистраций моделей** (листья графа первыми, владелец последним). Требуется актуальный `token`, в интерфейсе — ручной ввод slug. Никаких Roblox Cloud delete, удаления локальных FBX/PNG, удаления размещённых Studio моделей или удаления центральных Atlas Variants нет.
4. Устаревший токен отклоняется. Выполняется предварительная проверка незавершённых публикаций Real Estate. HTTP `DELETE` по старому маршруту остаётся совместимым и теперь по умолчанию сохраняет используемые общие текстуры.
5. При `preserve` **legacy** `estate:<slug>:<part>` и `location:<slug>` остаются стабильными адресами. В БД `.control-center/game1.db` создаётся `retained_shared_textures` с копией опубликованной идентичности/пути/хеша. Уже существующие `texture_atlas_bindings` сохраняются для реально используемого owner reference; если центральный атлас в дальнейшем успешно перепубликуется, сохранённая привязка по-прежнему может дать новый опубликованный ID по прежней политике Atlas Registry.
6. Регистрация нового владельца под занятым сохранённым slug блокируется, чтобы исходная ссылка не начала без согласия указывать на чужую текстуру. Модели, ссылающиеся на уже удалённый владелец, не переписываются.
7. Рабочие файлы и Roblox Asset ID не удаляются. Архивы регистраций: Real Estate → `.control-center/real-estate-retired/`, Location Assets → `.control-center/location-assets-retired/` (включая историю публикаций). При первой установке таблицы создаётся SQLite backup `.control-center/backups/before_m199_shared_retirement_*.db`.

## Ответственность

- `services/shared_asset_retirement.py` — планирование межреестровых зависимостей, токен подтверждения, оркестрация; не хранит текстуры.
- `services/retained_textures.py` — отдельные неизменяемые свидетельства опубликованной текстуры; не управляет моделями или Roblox.
- `real_estate/store.py` / `location_asset_store.py` — только собственные записи/архивы/выгрузки; читают сохранённые legacy ссылки и не меняют публикационный pipeline.
- `api/read_world.py`, `api/write_dispatch.py`, `api/delete_entities.py` — тонкие HTTP-адаптеры.
- `shared-asset-retirement.js` — общая модалка для двух разделов; `deco-assets.js` и `real-estate.js` только вызывают её.

## Проверки

- `test_shared_asset_retirement_m199.py`: реально записанные SQLite-профили, owner house→consumer door, собственный legacy PNG, Location→Location, Location→Estate, транзитивный cascade, stale token, реоткрытие БД, сохранение исходного файла и Image Asset ID.
- `test_shared_asset_retirement_ui_m199.py` + JS VM-тест: по умолчанию `preserve`, полный каскад только при ручном вводе slug и явном выборе `all`.
- Обновлены M130 и M169-валидаторы, отражающие новый контракт сохранения вместо старой блокировки.

## Оговорки

- `all` намеренно удаляет регистрации зависимых объектов, **не** фактически размещённые в Studio экземпляры и не облачные Roblox Assets. Архив перед удалением позволяет восстановить метаданные вручную.
- В разных SQLite-файлах Real Estate и Location Assets нет одной общей ACID-транзакции: предварительные проверки выполняются для всей цепочки; при неожиданном системном сбое между несколькими удалениями уже созданные архивы остаются, но повторять каскад нужно осмотрительно.
- Реальная Roblox Studio Sync/Play не запускалась. Контракты импорта, публикации, атласов и runtime не менялись.
