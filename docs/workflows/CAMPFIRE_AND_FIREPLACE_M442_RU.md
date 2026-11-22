# M442 · House Fireplace / Location Campfire — общий контракт

**Текущий источник истины:** `src/server/world/HouseFireplaceService.luau` (состояние и таймеры), `src/server/world/LocationCampfireService.luau` (размещённые костры), `src/server/world/HouseSocketService.luau` (дома), `src/shared/world/FireplaceMechanicsConfig.luau` (эффекты, события и настройки), `src/client/world/HouseFireplaceController.luau` (HUD).

## 1 · Авторские сокеты

- **Дом:** `fireplace_01_socket` — HEAD/передняя сторона Tail → Head. `chimney_01_socket` — только дым от этого дома. Сокеты дома принадлежат реестру House.
- **Location Asset `campfire_01`:** `fire_socket` — огонь и действия E/F; `cooking_pot_01_socket` — HEAD установки котла. Оба имени подтверждены в `assets/manifests/location-assets-fbx/campfire_01.json`; **не** добавляются в HouseSocketContract. Сервер берёт только опубликованные размещения из `EnvironmentAssetService.Observe`; неизвестные/дублирующиеся кости не подменяются координатами.
- **`cooking_pot_01`:** свой внутренний `cooking_pot_socket` для пара. Это сокет котла, не дома и не костра.

Для дома `HouseSocketAssetMount` переносит **grip → HEAD** через `BoneModelMount.Place`, со строго 0 studs clearance и `HouseSpawnOrientation.Upright`; MeshPart получают Appearance из Location Registry. У `campfire_01/cooking_pot_01_socket` направление кости вертикальное: горизонтальный вектор Tail → Head нулевой. Для котла используется точная HEAD-позиция этой кости и сохранённый горизонтальный heading размещённого `campfire_01`; произвольного Y-отступа нет. Никакой подмены реального FBX на Part-заглушку.

## 2 · Состояния, ресурсы, инварианты

| Состояние | Дом | Campfire |
|---|---|---|
| Пустой источник | E «Разжечь огонь», stub-расход 5 дерева | То же |
| Розжиг | `firewood_01` + Fire/Light, по умолчанию 120 c | Только Fire/Light, по умолчанию 120 с (без `firewood_01`) |
| По истечении огня | `embers_01` на 120 c, дым из трубы остаётся | Сразу `empty`, без углей |
| Котёл | Устанавливается только во время огня / дров (не на углях впервые) | Устанавливается во время горения на отдельный `cooking_pot_01_socket` |
| Ингредиенты | По stub-списку: −1 морковь, −1 лук, −1 картофель | То же |
| Готовка | По умолчанию 30 c на огне, 60 c на углях | 30 c на огне, без угольного этапа |
| Готово | Уведомление автору блюда независимо от расстояния; E забрать | То же |
| Котёл после затухания | Не удаляется; F убрать только когда пуст | То же |

- Розжиг, размещение котла, сбор блюда и списание заглушек происходят только после серверной проверки идентичности размещения, сокета, E/F, дистанции и cooldown. У клиента нет полномочий менять таймеры.
- Переключения выполняются по `Workspace:GetServerTimeNow()` и `fuelRevision`/`cookRevision`. Старая задача таймера не должна перескочить новый розжиг.
- Часы готовки фиксируются при добавлении ингредиентов; при окончании топлива они не сбрасываются. Инвентарь, реальные выдачи блюд, сохранение состояния после restart — **stubs/не реализованы**.
- Дым House (`HouseSocketEffects.StartSmoke`) создаётся выключенным. `BindChimney` связывает его с **этим** камином и включает только для `firewood` или `embers`. Отсутствие камина означает отсутствие дыма.
- Камерный ввод ПКМ не должен перекрываться прозрачным экранным фреймом. Action-панель одна, справа по центру на ПК, с крупными touch-кнопками на мобильном. Взаимодействия E/F выполняются по серверным `ProximityPrompt`.
- Статус источника показывается в **одной** нижней центральной панели, по умолчанию в пределах 50 studs; × скрывает до выхода из зоны, за её пределами панель скрыта автоматически. Никаких отдельных BillboardGui над объектами.

## 3 · Огонь и свет костра

На `fire_socket` приоритет имеют существующие **авторские** `Fire` и `PointLight` (настройки Fire Tuner из Studio, включая Size/Heat/TimeScale, RGB, Brightness/Range/Shadows). Их значения не перезаписываются: сервер меняет только `Enabled`. При отсутствии авторского компонента используется соответствующий fallback из `FireplaceMechanicsConfig`. Эффекты следуют за реальным Bone, ориентация пламени и пара — мировой +Y.

## 4 · Параметры Mechanics

**Control Center → Mechanics → House → Камин → Настройки**: времена дров, углей и костра; время готовки на огне и углях; расстояние отображения панели; радиусы использования/наведения костра. Единственный авторский источник — `config/mechanics/fireplace.json`, сохранение генерирует `src/shared/world/FireplaceMechanicsTuning.luau` (ограниченные числовые поля, контроль ревизии). Изменение требует Studio Sync и нового Play; игровая сессия не меняет параметры на лету. Пресеты Fire Tuner остаются независимо авторскими.

## 5 · Проверки

- `python -m unittest discover -s system/verify -p test_m442_campfire_status_shared_interaction.py -q`
- `python -m unittest discover -s system/verify -p test_m442_mechanics_fireplace_tuning.py -q`
- `python system/studio-plugin/validate_luau.py`
- `python system/verify/verify.py`

Отдельно проверить **Studio Play**: два дома с разными каминами, пустой дом, несколько `campfire_01` в разных Plot, E/F на ПК и мобильном, материал/Head-Pivot котла, авторские цвета/свет, дым при переходе в угли и потухании, звуковой/визуальный feedback, отсутствие блокировки ПКМ. Статические тесты не доказывают соответствие реального FBX и UI в Roblox Studio.
