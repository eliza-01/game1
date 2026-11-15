# Location Assets · Distance → LOD: этап 1

## Решение и границы

Новая ступень визуализации — дочерний ресурс `<slug>_lod1` (FBX и опубликованное имя Roblox). Контракты FULL, Material/Atlas, Collision Blueprint и Plots/Real Estate не меняются. FBX не может автоматически переименоваться в Blender при регистрации; внешнее имя проверяем, содержимое FBX не переписываем.

## Реализация этапа 1

1. Shared `world/LocationLodDistancePolicy.luau`: только расчёт желаемого состояния FULL/LOD1/UNLOADED, гистерезис против мигания, запрет невалидных параметров. По умолчанию 120 / 280 / 12 studs; это не итоговый профиль Low/Medium/High.
2. Client `world/LocationLodStudioProbe.luau`: Studio-only, CollectionService tag `Game1LocationLodProbe` на **одной тестовой Model**. Для камеры вычисляет расстояние и выводит Billboard `LOD policy: ...` и изменение состояния в Output; обход только помеченных экземпляров, не всего Workspace.
3. Никакого `Destroy()`, `Transparency`, изменения Pivot/Size/CFrame, подмены ServerStorage/Workspace, загрузки публичных ассетов или сетевых команд. Даже если state `UNLOADED`, существующая Model остаётся на месте.
4. Runtime визуальное переключение включать **только после** появления LOD1, доказанного соответствия FULL↔LOD1, отдельного каталога placements и правильного владения визуальными копиями клиентом.

## Ручная проверка в Roblox Studio (не нужен опубликованный LOD1)

В Edit Mode выбери в Explorer **ровно одну Model** типа Location Asset. В Command Bar выполни:

```lua
local selected = game:GetService("Selection"):Get()
assert(#selected == 1 and selected[1]:IsA("Model"), "Select one Model")
game:GetService("CollectionService"):AddTag(selected[1], "Game1LocationLodProbe")
```

Запусти **Test → Play**. Подходи к отмеченному ассету и отходи за 120, затем 280 studs; затем вернись назад. Переключение при движении назад использует границы 108 и 268 studs; при удалении — 132 и 292. Белая надпись показывает **вычисленное состояние, а не текущую отрисованную модель**. Коллизия и геометрия не должны изменяться.

Чтобы снять отладочный тег после остановки Play:

```lua
local selected = game:GetService("Selection"):Get()
assert(#selected == 1 and selected[1]:IsA("Model"), "Select one Model")
game:GetService("CollectionService"):RemoveTag(selected[1], "Game1LocationLodProbe")
```

В `Server & Clients` можно проверить разные состояния на двух клиентах, но полноту передачи ассетов и память пока тестировать нечего. Останови Play — созданные локальные BillboardGui удалятся вместе с клиентом.

## Дальше

После первого LOD1 проверяем опубликованный Model ID, геометрический anchor/Pivot относительно FULL, материалы, отдельную доставку визуальных данных, замену FULL↔LOD1, выгрузку/возврат без повреждения серверной коллизии и тест памяти на телефоне. Утверждённые названия будущих патчей не фиксируем.


## Studio Probe: standalone bootstrap fix

`Game1LodProbeClient` is now an independent `LocalScript` under `StarterPlayerScripts`, separate from the main `Game1Client` initialization sequence. The client always prints `[game1][LOD probe] Standalone client starting` when Studio Play launches.

In **Test → Play** (not Edit mode), the upper-left overlay displays `LOD Probe | ACTIVE` and the number of tagged Models currently replicated to the client. A `0 visible tagged Models` message means the client cannot currently see a tagged Model (e.g., it was streamed out, or the tag was not present in the running session). The target model receives a BillboardGui after it is available.

This update changes only the Studio diagnostic. No geometry, placement, collision or LOD visuals are modified.


## Studio Probe: deferred geometry (Streaming)

`CollectionService` может вернуть помеченную Model до появления её вложенных `BasePart` на клиенте. Отсутствие `BasePart` в момент запуска не означает отсутствие геометрии в Place.

Probe теперь регистрирует такую Model в состоянии ожидания и каждые 0,25 секунды повторяет обнаружение геометрии (до 32 тестовых моделей, только Studio). При появлении `BasePart` подключает BillboardGui и начинает считать дистанцию и состояния. При выгрузке геометрии оставляет регистрацию и автоматически возобновляет наблюдение при повторной загрузке.

Индикатор различает число моделей с тегом (`tagged`) и число моделей с загруженной геометрией (`ready`). Если `ready = 0` даже в непосредственной близости, нужно проверить репликацию и структуру Model на клиенте, а не менять Pivot или визуальные ассеты.

Никаких изменений в Asset Registry, коллизиях, размещениях, FULL/LOD1 или серверном Streaming этот диагностический патч не производит.
