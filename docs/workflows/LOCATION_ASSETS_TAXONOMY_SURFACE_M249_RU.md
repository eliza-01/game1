# M249 · Location Assets — категории и материалы поверхности

## Область

Только Location Assets / DecoManager / Place Registry. Real Estate, NPC, Characters,
монстры, оружие и генератор домов не получают новых правил или изменений материала.

## Категории

ID категории в SQLite — канонический **singular**; множественное число ранее
использовалось только для подписей/папок Studio. Существующие ID не мигрируют.

| Группа | Категории в постоянном порядке |
|---|---|
| Flora | tree, bush, flower, rock |
| Structure | light, fence, ladder, bridge, pillar, post |
| Prop | prop, decoration, building |

`post` размещён в Structure, поскольку отдельная группа для него не была задана.
Единственный исходный каталог и порядок для HTTP и Asset Manager:
`system/control-center/services/location_asset_taxonomy.py`.
`DecoManager` использует те же стабильные значения категорий и названия в единственном числе;
старые папки Studio (`Trees`, `Fences` и прочие) сохраняются, Place не переносится.
Новый выбор категории в Asset Manager показывает три колонки, а значение остаётся
обычным `select` с событиями `change` для совместимости с формами.

## Материал и звуки

`surface_material` — отдельное поле Location Asset в SQLite (`default` для старых строк).
Это стабильный *семантический* ID, не категория, не атлас и не `MaterialVariant`.
Справочник сопоставляет semantic material → `Enum.Material` → `soundFamily`.
Например, `wood → Wood → wood`, `rock → Rock → stone`, `foliage → LeafyGrass → foliage`.

В `LocationAssetRegistry` публикуются `surfaceMaterial`, `robloxMaterial`, `soundFamily`;
`src/shared/world/LocationSurfaceMaterialResolver.luau` даёт read-only API для будущих
эффектов удара, передвижения и взаимодействий без зависимости от Studio-плагина.
**Никакие звуки или события сами по себе не запускаются.**

Студийный `MeshPhysicsCore.ApplyLocationSurfaceMaterial` назначает одинаковый
`Game1LocationSurfaceMaterial` и (для выбранного не-default значения) `MeshPart.Material`
всем визуальным и коллизионным MeshPart конкретного Location Asset. `col_mesh` остаётся
невидимым и сохраняет Precise коллизию, CanCollide и свои размеры. Для `default`
старый `MeshPart.Material` **не** переписывается. SurfaceAppearance/Atlas также не меняются.

Новые размещения через DecoManager наследуют материал сразу. Существующие модели
**не изменяются при сохранении Identity**: Place Registry Scan сравнивает материал
с текущим каталогом; `Sync`, `Sync group` и `Sync all` используют ранее реализованные
явные подтверждения, ChangeHistoryService/Undo и журнал. Для старой модели,
которой нужен Repair структуры, можно применить материал в ходе отдельного Repair.

## Данные и миграция

- Версия Registry и manifest повышена с 4 до 5, Place Registry protocol v1 расширен
  необязательным полем `needsMaterial`.
- При первом старте Host Agent создаётся SQLite-backup в `.control-center/backups/`
  и добавляется `location_assets.surface_material TEXT NOT NULL DEFAULT 'default'`.
- Никакие Image ID, Model ID, Mesh ID, атласы и история публикаций не меняются.
- Переназначение материала в Identity — metadata-only revision, Open Cloud не вызывается.
- Ранее сгенерированные манифесты v4 могут существовать до первого миграционного
  запуска; `LocationAssetStore.export()` регенерирует их из авторитетной базы.

## Проверка в Studio на копии Place

1. Выбрать `wood` у тестового Location Asset в Identity → Apply Changes.
2. Сделать `Scan Place`: у старого управляемого экземпляра должен появиться
   статус «Материал требует Sync», даже если Mesh и Texture актуальны.
3. Сделать одиночный `Sync`, проверить `Game1LocationSurfaceMaterial=wood`
   и `Material=Wood` и на visual, и на `col_mesh` (его `CanCollide` не меняется).
4. Выполнить Undo и проверить восстановление прежнего материала и атрибута.
5. Проверить новый Place через DecoManager — материал сразу назначен обеим частям.

Статический preflight не подтверждает реальную физику/Undo в Roblox Studio.
