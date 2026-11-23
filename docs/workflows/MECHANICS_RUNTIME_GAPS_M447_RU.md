# M447 · Аудит Mechanics: неполные контракты, хранение и проверка Runtime

**Сверка:** 23.11.2026, исходное дерево после M446. **Характер изменения:** документация Control Center → Mechanics и этот аудит; игровой код, данные игроков, ассеты, зарегистрированные ID и логика Runtime не изменяются.

## Как читать статусы

- **Реализовано в исходниках** означает наличие серверного/клиентского кода и контракта, **не** автоматическую приёмку в опубликованной игре.
- **Авторские данные сохраняются** — SQLite/JSON/Luau-манифест и настройки Game1, которые разработчик синхронизирует с Studio и публикует. Это **не** `DataStoreService` и не сохранение состояния конкретного игрока или отдельного live-экземпляра.
- **Сессионное состояние** — таблицы Lua, атрибуты Model/Player, `task.delay`, текущий GUI. После уничтожения экземпляра или запуска другого сервера оно не обязано восстанавливаться.
- **Не проверено** означает отсутствие в этом аудите настоящего Studio Play/Device Simulator/опубликованного Roblox Place теста. Статические Python-тесты не могут подтвердить FBX pivot, сетевую картинку или реальный Runtime Build.
- Дефект/долг фиксируется **по наличию отсутствующего контракта**, а не объявляется уже воспроизведённой ошибкой. Ничего не помечается `DONE` без приёмки.

Каталог Mechanics содержит 21 *общую* карту: **House 10**, **NPC 3**, **Monster 3**, **Character 5**. Индивидуальные скрипты для каждого asset slug пока не каталогизированы; нельзя приписывать им общую карточку как личную. Каждая карта открывается со списком соответствующих исходников и разделом **«Недостающее / проверить»**. Эта матрица охватывает также общие подсистемы, не имеющие своей вкладки Mechanics, чтобы долги не терялись.

## 1. Матрица долгов по игровым механикам

| Система | Фактический владелец в исходниках | Не хватает для завершения / готовности MMO | Реальная проверка |
| --- | --- | --- | --- |
| House socket routing, AIM/USE | `HouseSocketService`, `HouseSocketContract` | Контракт повторной регистрации со state-rehydration; согласованная идентичность дома/сокета | Живой дом, Streaming, повторный Register, два клиента |
| Дверь | `HouseDoorService`, `HouseSocketService` | Сохранение открыто/закрыто, права жильцов/владельца, восстановление pivot | Открытие с двух сторон, физика/коллизии, reload |
| Padlock | `HousePadlockService`, `HouseSocketEffects` | Реальный предмет-ключ, авторизация, постоянная блокировка, модель замка вместо Part | Два игрока с разными правами, logout/login |
| Лифт / spawn | `HouseElevatorService`, `HouseSpawnOrientation`, `CharacterCameraSync` | Сохранённая точка возвращения, политика safe landing; физического лифта нет | 1–3 этаж, heading Bone, ПКМ, Mobile, Streaming |
| Chest | `HouseSocketService` | Inventory, loot table, транзакция выдачи, повторный доступ, права, сохранение | Два игрока, быстрые повторы E/F, reconnect |
| Камин / campfire | `HouseFireplaceService`, `LocationCampfireService` | Durable state топлива, котла, ready/cooking, ownership, восстановление после Unregister/перезапуска | Два дома/костра, фазы топлива, удаление/появление сокета |
| Cooking | `HouseFireplaceService` | Настоящий atomic consume/grant; owner/party-доступ; heat-aware таймер (переход fire→embers/empty) | Уголь в середине готовки, пустое топливо, два игрока, повторный сбор |
| Chimney / Fire / steam | `HouseSocketEffects`, `HouseFireplaceService` | Нет отдельной persistence (должна выводиться из сохранённого состояния топлива); согласование authored Fire/PointLight | Fire Tuner presets, HEAD, world-up, Client Streaming |
| Houseplants / plots | `HouseSocketContract` и authoring Real Estate | Система растений/выращивания и MMO-владение/купля/права участка не реализованы | Runtime Build сокетов и pivot после замены дома |
| NPC spawn / death | `NpcSpawnerService`, `DeathLifecycleService` | Persistent HP/position, respawn clock, сущность NPC между серверами | Spawn-слоты, смерть, повторное появление, Studio+publish |
| NPC combat / home | `NpcCombatAIService`, `ActorHomeLeash` | Durable threat/target/timers; multiplayer combat arbitration | Damage during Return, navigation on Terrain, leash |
| NPC animation / equipment / UI | `NpcAnimationService`, `NpcEquipmentService`, `NpcOverheadController` | Живые смены состояния/инвентаря не сохраняются, per-asset cards отсутствуют | Два клиента, Streaming, clipping, разное оружие |
| Monster population / death | `MonsterPopulationController`, `MonsterSpawnerService` | Persistent respawn schedule, live population/HP; loot/XP/quest events | Несколько смертей, maxAlive, respawn spacing |
| Monster AI / attack | `MonsterAIService`, `MonsterAttackExecutor`, actor helpers | Durable aggro/combat/return; подтверждённая reward pipeline | Pursuit species, damage timeout, navigation & hit timing |
| Character assembly / stats | `CharacterService`, `CharacterStatsService` | Account profile: character selection, HP/stats, progression, save/logout/rejoin | Два игрока, reconnect, failed rig load |
| Character movement / camera | `MovementController`, `CameraController`, `MobileInputController` | User-level preferences/checkpoints, gamepad/accessibility acceptance | ПКМ, touch, pinch, avatar collision, hybrid UI |
| Weapon selection / melee / bow | `WeaponSelectionService`, `AttackService`, `BowHitscanService`, `WeaponEquipService` | Persistent ownership/inventory, equip entitlement, ammo/loot if required | Server hit validity, close target, headshot, latency, mobile |
| Character HP / death / return | `DamageService`, `CharacterRegenerationService`, `CharacterService` | Session-to-account save for HP/death/revive/checkpoint, anti-duplicate transitions | Death/DeathIdle, Return to Town, simultaneous remotes |
| Animation / attachments | `CharacterAnimationController`, `BoneMountedAttachmentController`, `BoneModelMount` | Asset-specific acceptance и цельный процесс публикации; per-player visual changes need own save policy | Bone following, multi-Mesh hair, two clients, streaming |
| UI status / feedback | `InformativeWindowDock`, `HouseFireplaceController`, `FloatingResourceFeedback`, `UiPresentationSettings` | User-specific preference save not implemented; +N/−N currently **не доказательство** изменения инвентаря | Свернуть/открыть, respawn head, text padding, ПК/Mobile |

## 2. Сквозные подсистемы за пределами четырёх вкладок

### Location assets, world streaming, Real Estate

- **Есть код:** `EnvironmentAssetService`, `LocationLodTemplateService`, `LocationWorldStreamer`, `LocationCampfireService` и authoring pipeline Runtime Place. Опубликованные модели/реестры и LOD-профили относятся к **проектному authoring**, не к персональной игре пользователя.
- **Не зафиксировано как выполненное:** восстановление произвольных изменённых игровых world-объектов, купленного участка и размещённых игроком предметов из сервера в сервер; полноценный тест текущего `.rbxlx` после M446. При компиляции нельзя терять серверные socket Bone/Attachment или связи Location Campfire; LOD визуала не должен сбрасывать состояние источника тепла.
- **Принять отдельно:** save Studio Place → verified backup → Runtime Build → Play compiled place, house/campfire E/F, два клиента, StreamingEnabled, LOD переключения, Model/Atlas и Material.

### Настройки, публикация, инструменты отладки

- **Сохраняется в файлах проекта:** `assets/manifests/options.json` → `src/shared/GameOptionsRegistry.luau` (включая PC/Mobile UI); `config/mechanics/fireplace.json` → `FireplaceMechanicsTuning.luau`; реестры Location/NPC/Monster/Character/Weapon, generated spawn records. Сохранение в Control Center требует синхронизации и публикации актуального Place.
- **Не сохраняется автоматически в игру:** локальный Studio UI Debug preview, выбранная в конкретной клиентской сессии свёрнутость окна, текущие `task.delay`, runtime-атрибуты модели и изменение визуального +N/−N.
- **Dev vs published:** Studio debug и test loadout не должны считаться производственным игроковым интерфейсом прогрессии/инвентаря. PublishedDebugAccess и прочие проверки должны тестироваться в published Place с обычными правами.

### Канал вознаграждений / инвентарь

В просмотренных игровых `src/server` отсутствуют вызовы `DataStoreService`, `GetDataStore`, `GetAsync`/`SetAsync`/`UpdateAsync`. Это **проверка среза M446**, а не доказательство того, что в произвольных Roblox-скриптах вне проекта не существует другого сохранения. Ветви костра делают `notify(kind="resource")`, но нет атомарного изменения постоянного баланса. Не проектировать отдельный inventory внутри камина, NPC, монстра или сундука: нужен общий authoritative сервис с идемпотентными spend/grant, журналом транзакций, восстановлением и авторизацией.

### Приоритет рисков

1. **Блокер MMO-персистентности:** account inventory/stats/ownership, долговременный world-state и атомарная выдача наград — отдельный согласованный контракт, прежде чем включать цены/loot.
2. **Блокер целостности механики:** сохранение/восстановление состояния heat-source, повторная регистрация socket, heat-aware cooking, правило `cookOwner` vs общий доступ к блюду.
3. **Блокер опубликованной приёмки:** Runtime Place после M446 не был получен и запущен в ходе этого аудита; все визуальные, навигационные и мобильные проверки остаются открытыми.
4. **Документационный долг:** на данный момент NPC/Monster/Character карты общие; индивидуальные per-asset записи, исходники и версии добавляются только после обнаружения/регистрации конкретных авторских скриптов.

### Зафиксированные долги тестовой инфраструктуры (срез до M447)

В дереве M446 **уже** падают некоторые исторические suites; M447 не изменяет их реализацию, чтобы не смешивать аудит документации с рефакторингом:

- `test_m337_npc_home_options.py`: ожидает шесть секций Options, а после добавления UI их семь (`6 != 7`).
- `test_character_assemblies.py`: старые фикстуры деталей `newborn_upper` и т.п. отклоняются текущим правилом имён `human_*_m001_*`.
- `test_character_attack_cadence_m206.py`: один прежний контракт атаки и одна нормализация timing уже расходятся с текущим кодом.
- `test_character_animation_boundaries_m189.py`: старая фикстура не проходит требование `character assemblies initialized`.

Эти провалы воспроизведены на **неизменённом M446**, отдельно от патча M447. Их нельзя ни выдавать за регрессию документации, ни скрывать под формулировкой «все тесты зелёные». Для каждого — самостоятельное обновление фикстур либо выяснение игрового расхождения до закрытия карточки.

## 3. Как фиксировать завершение, не переписывая историю

Для **каждой карты** после реальной реализации заполнять: владелец server state; persistent key и schema version; восстановление при `Start`/`Register`/Streaming; события save/flush и idempotency; права и anti-duplication; кто имеет право менять состояние; поведение при ошибке сети/хранилища; ограничения производительности; результат Play в Studio, на двух клиентах, на Mobile и на опубликованном Runtime Place. Статусы `implemented` / `static verified` / `Studio verified` / `published verified` отдельно. Не писать в Kanban `DONE` по одному наличию файлов.

Проверки M447 охватывают: все четыре вкладки и их разрешённые source keys, все 10 карт House и 11 actor/player карт с открытыми ограничениями, отсутствие небезопасного произвольного чтения файлов, неизменность `src/` и конфигурации. **В этой задаче не запускался Roblox Studio**; актуальные `Save to File .rbxlx` и live DataStore не проверялись.

### Привязка к текущим контрактам

- [Mechanics House M436](MECHANICS_HOUSE_CATALOG_M436_RU.md) и **Control Center → Mechanics** — краткие актуальные карты с исходниками.
- [Камин / костёр M442](CAMPFIRE_AND_FIREPLACE_M442_RU.md) — порядок действий, конфигурация и Socket HEAD.
- [UI profiles M443–M446](UI_PRESENTATION_OPTIONS_M443_RU.md) — отдельно сохранение проекта, Preview и сессионный UI.
- [NPC Home M337](M337_NPC_HP_MONSTER_HOME_OPTIONS_RU.md), [Monster Pursuit M338](M338_MONSTER_PURSUIT_SPECIES_RU.md), [Mobile M432](MOBILE_CONTROLS_M432_RU.md).
- [Текущее ТЗ](../spec/CURRENT_PROJECT_SPEC_RU.md), [текущая архитектура](../architecture/CURRENT_ARCHITECTURE_RU.md), [Kanban](../kanban/STATUS_2026-11-22_M439.md).
