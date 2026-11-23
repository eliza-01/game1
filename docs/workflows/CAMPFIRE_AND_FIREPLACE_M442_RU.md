# M442 · House Fireplace / Location Campfire — общий контракт

**Текущий источник истины:** `src/server/world/HouseFireplaceService.luau` (состояние и таймеры), `src/server/world/LocationCampfireService.luau` (размещённые костры), `src/server/world/HouseSocketService.luau` (дома), `src/shared/world/FireplaceMechanicsConfig.luau` (эффекты, события и настройки), `src/client/world/HouseFireplaceController.luau` (данные HUD), `src/client/world/InformativeWindowDock.luau` (общая оболочка информативных окон).

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
- Статус источника показывается в **общем** нижнем контейнере информативных окон `InformativeWindowDock`: только когда игрок одновременно находится в USE-радиусе сокета, смотрит в его AIM-зону центральным прицелом и видимость не перекрыта стеной (M448). `ProgressVisibleRadius` (по умолчанию 50 studs) остаётся дополнительным верхним пределом, но не отменяет USE-радиус. Шеврон вниз сворачивает содержимое, компактная нейтральная кнопка «Инфо» со шевроном вверх около атаки разворачивает его без выхода из зоны. За пределами радиуса оба элемента скрываются автоматически. Никаких отдельных BillboardGui над объектами. M446 заменил кнопки ✓ / 🔥 из M445.

## 3 · Огонь и свет костра

На `fire_socket` переиспользуются существующие **авторские** `Fire` и `PointLight` (Fire Tuner), без создания дубликатов. **Обновление M443:** оба компонента получают активный игровой пресет из `FireplaceMechanicsConfig`: без котла — `CampfireFire` и `CampfireLight` по референсу костра; с котлом — `Fire` и `Light` как у камина. При снятии котла возвращается референс, таймер горения сохраняется. Вызовы не включают погасший огонь повторно. Эффекты следуют за реальным Bone, ориентация пламени и пара — мировой +Y.

## 4 · Параметры Mechanics

**Control Center → Mechanics → House → Камин → Настройки**: времена дров, углей и костра; время готовки на огне и углях; расстояние отображения панели. Источник — `config/mechanics/fireplace.json`, который генерирует `src/shared/world/FireplaceMechanicsTuning.luau`. **M449 переносит постоянные USE/AIM-радиусы дома и костра в Options → Sockets** (`assets/manifests/options.json` → `src/shared/GameOptionsRegistry.luau`). При первом обновлении параметры CampfireInteractionRadius/CampfireAimRadius мигрируют из Mechanics в Options; старые поля Mechanics остаются в JSON для совместимости, но больше не управляют игровыми зонами. Изменения требуют синхронизации Rojo и нового Play; Studio HS Debug временно переопределяет значения только для игрока. Подробности: [M449 · Socket Ranges](SOCKET_RANGES_OPTIONS_M449_RU.md). Пресеты Fire/Light выбираются по наличию котла согласно M443; Fire Tuner сохраняет сами экземпляры эффектов.

## 5 · Проверки

- `python -m unittest discover -s system/verify -p test_m442_campfire_status_shared_interaction.py -q`
- `python -m unittest discover -s system/verify -p test_m442_mechanics_fireplace_tuning.py -q`
- `python system/studio-plugin/validate_luau.py`
- `python system/verify/verify.py`

Отдельно проверить **Studio Play**: два дома с разными каминами, пустой дом, несколько `campfire_01` в разных Plot, E/F на ПК и мобильном, материал/Head-Pivot котла, авторские цвета/свет, дым при переходе в угли и потухании, звуковой/визуальный feedback, отсутствие блокировки ПКМ. Статические тесты не доказывают соответствие реального FBX и UI в Roblox Studio.


## Незавершённые условия для MMO Runtime · M447

**Это не новые реализованные функции.** Для конкретных подтверждений и всех доменов см. [аудит Mechanics M447](MECHANICS_RUNTIME_GAPS_M447_RU.md).

1. Состояния `states[Model]` в `HouseFireplaceService`, fuel/cook end timestamps, `cookOwner`, живые модели котла и топлива **не** сохраняются в DataStore и теряются при `Unregister`/рестарте сервера. Persisted authoring JSON/Studio Place содержит *настройки*, но не эти состояния.
2. Уведомления расхода −5 дерева, −1 ингредиентов и получения +1 блюда **не проводят реальную транзакцию инвентаря**. Требуется один общий серверный inventory/ledger, идемпотентный spend/grant и политика прав.
3. `startCooking` устанавливает однократный `task.delay`: при переходе firewood→embers готовка не замедляется, при потухании не приостанавливается. Согласовать heat-aware накопление прогресса и восстановление после reload.
4. Готовое блюдо в `Interact` может собрать любой подошедший игрок: `cookOwner` используется для уведомления, но не является проверкой права получения. Явно определить owner/party/public policy.
5. В `LocationCampfireService.clear` тоже вызывается `Fireplace.Unregister`, поэтому при пересоздании опубликованного костра возможен сброс live-прогресса. Требуется стабильная идентичность размещения и rehydration независимо от LOD визуала.
6. Проверить в Roblox Studio и собранном Runtime Place: сокеты HEAD, реальные pivot, shared light/Fire presets, дым в переходах и мультиклиентский UI, без автодоказательств по статическим тестам.

## M448 · House / Campfire Socket Studio Debug и AIM-интерфейс

- **House:** `fireplace_01_socket` теперь AIM-enabled (`USE 8 studs`, `AIM 4 studs` по умолчанию), как авторские `chest_01_socket` и Elevator. Изменение `hoverRadius` является частью `HouseSocketContract`; серверный USE-контроль при этом не ослабляется.
- **Location `campfire_01`:** отдельный `CampfireSocketContract`. `fire_socket` — интерактивный сокет (`USE` и `AIM` из Options → Sockets, с fallback из `FireplaceMechanicsTuning` до генерации Options); `cooking_pot_01_socket` — **только HEAD marker** позиции котла, у него нет самостоятельной USE/AIM зоны. Эти сокеты не включены в House Registry.
- **Studio Play → HS:** единая панель `HOUSE / CAMPFIRE SOCKETS`: REFRESH возвращает присутствие сокетов ближайших домов и зарегистрированного костра; `RANGES` рисует зелёную USE-сферу, янтарную AIM-сферу и маленькую голубую точку HEAD котла. Отрисовка ближайших сокетов ограничена бюджетом; Part-превью `CanQuery=false`, `CanCollide=false`, `CanTouch=false` и не участвуют в попаданиях/физике. `+ / −` изменяют per-player Studio overrides, не сохраняют редакторский FBX/JSON и не распространяются на других игроков.
- **Геймплей:** панели E/F и `InformativeWindowDock` используют один принцип наведения — луч из `CameraController.CursorPoint()` через `HouseSocketAimPolicy.RaySphereEntry`, с проверкой `HouseSocketAimOcclusion`, плюс дистанция от `CharacterSpatialRoot` до сокета. Отсутствие разрешённого действия во время готовки не блокирует чтение информационных строк. При уходе из USE-зоны панель и кнопка восстановления исчезают; при отворачивании — временно скрываются без сброса состояния сворачивания.
- **Вне рамок:** никаких изменений Fire/Light, времени горения, persistence, моделей, размещений или инвентаря. Статические тесты не подтверждают фактическое наведение в Studio Play; проверь на ПК с RMB и на мобильном с центральным курсором, а также при двух рядом стоящих кострах.
