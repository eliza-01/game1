# ТЗ — НОВЫЙ ROBLOX PLACE НА ЧИСТОЙ БАЗЕ С ИНФРАСТРУКТУРОЙ ПО ОБРАЗЦУ ROBLOXLINEAGE

**Статус:** стартовое техническое задание / baseline  
**Назначение:** создать новый независимый Roblox-проект, используя удачные инфраструктурные решения RobloxLineage, но без зависимости от Lineage II, Interlude и их данных.  
**Рабочее имя проекта:** `game1`  
**Рабочий slug:** `game1`

---

## 1. Цель

Создать новый Roblox Place как **полностью отдельный проект**, который:

- использует тот же общий инженерный подход к ведению проекта, что и RobloxLineage;
- имеет собственный Git/Rojo/runtime/Control Center/Asset Manager/backup/verify контур;
- не зависит от данных, схем, справочников, ассетов и игровых правил Lineage II;
- стартует с чистой базы контента;
- позволяет переносить функциональные разделы Asset Manager из RobloxLineage постепенно, по одному;
- первым реализует раздел **Characters**;
- на первом playable baseline сохраняет уже проверенный подход к custom character runtime, камере, перемещению и атаке;
- использует новую упрощённую систему игровых статов.

Новый проект должен быть sibling-проектом, а не продолжением базы RobloxLineage.

---

## 2. Ключевой принцип миграции

RobloxLineage используется только как **референс архитектуры и проверенных технических решений**.

Нельзя копировать проект целиком с последующим постепенным удалением Lineage-зависимостей.

Правильная модель:

> создать чистую структуру проекта и переносить в неё только конкретные универсальные компоненты после проверки их зависимостей.

Каждый переносимый модуль должен отвечать на два вопроса:

1. Является ли он универсальным для нового проекта?
2. Не содержит ли он скрытых предположений о Lineage/Interlude, race/class/sex, конкретных skeleton names, weapon families, source databases и Combat V2?

Если содержит — зависимость должна быть удалена или компонент должен быть переписан до включения в новый проект.

---

## 3. Жёсткая изоляция от RobloxLineage

Новый проект обязан иметь собственные:

- корневую директорию;
- Git repository;
- `default.project.json`;
- Rojo server;
- имена контейнеров DataModel;
- Docker Compose project;
- Docker image/container;
- Docker network;
- persistent state;
- Asset Manager data;
- manifests;
- database/state store;
- `.env.local`;
- Open Cloud configuration;
- Studio bridge;
- Control Center host agent;
- порты;
- логи;
- backup root;
- snapshot history;
- recovery inventory;
- generated runtime files;
- verification reports.

Запрещены:

- чтение manifests напрямую из RobloxLineage;
- запись в RobloxLineage;
- общая writable database;
- общий writable Docker volume;
- общий backup namespace;
- общий `.control-center`;
- использование путей вида `E:\RobloxProjects\RobloxLineage` внутри нового runtime/tooling;
- использование имени `RobloxLineage` как project identity в JSON/Luau/API contracts;
- скрытые fallback-и на данные старого проекта.

Оба проекта должны иметь возможность быть запущены одновременно без конфликтов.

---

## 4. Что НЕ переносим

На стартовом этапе в новый проект **не переносятся**:

- Interlude databases;
- `weapongrp`, `armorgrp`, `npcgrp`, `skillgrp`;
- PTS/L2OFF databases;
- Combat V2 reference/oracle data;
- Lineage race/class/sex catalog;
- Lineage-specific character prefixes (`FFighter`, `MElf`, `FDarkElf` и т. п.) как системная идентичность;
- Lineage weapon families и animation taxonomy;
- armor/monster/NPC/building/sound/quest databases;
- существующие Asset Manager sections из RobloxLineage;
- старые item/weapon/armor/monster/NPC manifests;
- специальные правила Lineage skeleton/socket/texture naming;
- игровые формулы Lineage;
- старые Character stats/professions;
- любые автоматически сгенерированные registry из Interlude.

Имена и структуры нового проекта должны быть предметно нейтральными.

---

## 5. Что переносим как основу

Допускается перенос после очистки зависимостей:

- общая организация `src/client`, `src/server`, `src/shared`;
- организация project-coupled tooling через `system/`;
- Rokit + Rojo workflow;
- Control Center как локальный control plane;
- Web Asset Manager shell;
- Windows host-agent;
- Studio bridge/plugin подход;
- backup/snapshot/verify/recovery подход;
- hashing и atomic writes;
- source/prepared/publication/reimport принципы;
- asset ownership/recoverability принципы;
- custom character runtime;
- `RootCollider + NavigationRoot + ControllerManager`;
- scripted camera;
- camera-relative movement;
- базовый attack pipeline;
- server-authoritative damage;
- input bindings;
- generic hitbox/feedback infrastructure, если она не содержит Lineage-specific assumptions.

---

## 6. Предлагаемая стартовая структура

```text
[PROJECT_ROOT]/
  assets/
    source/
      characters/
    prepared/
      characters/
    manifests/
    reports/

  config/

  docs/

  generated/

  place/
    game1.rbxl
    snapshots/

  src/
    client/
    server/
    shared/

  system/
    asset-manager/
    control-center/
    asset-sync/
    backup/
    restore/
    studio-bridge/
    studio-plugin/
    verify/
    migrations/
    lib/

  .control-center/
  .env.example
  .gitignore
  .gitattributes
  default.project.json
  rokit.toml
  sync.ps1
  control-center.ps1
  control-center-stop.ps1
  README.md
```

На старте не создавать пустые предметные подсистемы вроде `monster-database`, `armor-database`, `sound-database` только ради сходства со старым проектом.

Новая структура должна расширяться по мере реальной миграции разделов.

---

# ЭТАП 1 — TOOLCHAIN И ПУСТОЙ PLACE

## 7. Rojo / Rokit

Настроить Rokit и Rojo как независимый toolchain нового проекта.

Baseline:

```toml
[tools]
rojo = "rojo-rbx/rojo@7.7.0"
```

Версию можно позже обновлять отдельно, но стартовая миграция должна минимизировать лишние изменения.

`default.project.json` должен:

- иметь новое имя проекта;
- маппить `src/shared` в собственный namespace в `ReplicatedStorage`;
- маппить `src/server` в собственный namespace в `ServerScriptService`;
- маппить `src/client` в собственный namespace в `StarterPlayerScripts`;
- устанавливать `Players.CharacterAutoLoads = false`;
- отключать стандартный PlayerModule, если сохраняется текущая custom-character схема;
- не содержать `RobloxLineageShared`, `RobloxLineageServer`, `RobloxLineageClient`.

Пример нейтральных namespace:

```text
ReplicatedStorage.[Project]Shared
ServerScriptService.[Project]Server
StarterPlayerScripts.[Project]Client
```

---

## 8. Новый Place

Создать чистый `place/game1.rbxl`.

В нём на baseline достаточно:

- Baseplate / тестовой сцены;
- SpawnLocation;
- минимального освещения;
- runtime containers, создаваемых Rojo;
- никакого игрового контента Lineage вручную.

Place не должен быть копией старого RobloxLineage Place.

---

# ЭТАП 2 — ОТДЕЛЬНЫЙ CONTROL CENTER / DOCKER / DATA

## 9. Docker

Новый проект получает собственный `compose.yaml`.

Требования:

- отдельный `container_name`;
- отдельное имя Compose project;
- отдельные порты;
- никакого конфликта с RobloxLineage;
- отдельный network;
- отдельный persistent volume/state, если используется;
- root path должен указывать только на новый проект;
- host agent должен валидировать project identity перед mutating operation.

Порты RobloxLineage не переиспользовать.

В частности новый проект не должен занимать его текущие:

```text
43720
43721
34872
43127
```

Номера новых портов должны быть заданы централизованно в config/env, а не размазаны hardcode по Python/PowerShell/JS.

---

## 10. Отдельная база / persistent state

Под «отдельной БД» понимается полная логическая и физическая изоляция данных нового проекта.

Если Asset Manager продолжает manifest-first подход:

- все manifests создаются с нуля;
- project identity новая;
- данные RobloxLineage не импортируются;
- старые manifests не используются как fallback.

Если отдельные функции используют локальную БД/SQLite/state store:

- создать отдельный файл/volume нового проекта;
- отдельную schema initialization;
- никаких shared writable tables/files;
- migration history независимая.

На первом этапе **не требуется менять manifest-first архитектуру на SQL только ради наличия БД**. Главное требование — отдельный источник состояния и отсутствие общего состояния с RobloxLineage.

---

# ЭТАП 3 — ЧИСТЫЙ ASSET MANAGER

## 11. Asset Manager v1

Asset Manager нового проекта должен стартовать как **чистая оболочка**.

На первом этапе в нём разрешён только один предметный раздел:

> **Characters**

Не показывать даже пустыми:

- Weapons;
- Armor;
- Monsters;
- NPC;
- Sounds;
- Animations;
- Buildings;
- Zones;
- Quests;
- Items;
- Arrows;
- Interlude Database;
- прочие RobloxLineage-specific tabs.

Разделы будут переноситься отдельно последующими задачами.

Общий shell можно сохранить:

- navigation;
- operation status;
- logs;
- file picker;
- source ingest;
- hashing;
- publish/reimport transaction infrastructure;
- Studio status;
- Rojo status;
- safe operation locking.

---

# ЭТАП 4 — CHARACTERS

## 12. Character — новая предметная модель

Сохранить концепцию **Character Archetype**, но убрать Lineage identity.

В новой системе архетип не обязан иметь:

- race;
- class;
- sex;
- profession;
- Lineage prefix;
- Interlude identity;
- Lineage animation archetype.

Минимальная identity:

```text
archetypeId
displayName
```

`archetypeId` — стабильный безопасный slug, например:

```text
default
warrior
mage
test_character
```

Он не должен кодировать структуру `race/class/sex`.

---

## 13. Один archetype = одна модель

В Character Asset Manager v1:

- один archetype;
- одна зарегистрированная character model;
- один model source;
- один canonical ServerStorage model;
- без armor composition;
- без набора body parts;
- без отдельных race/class profiles;
- без Lineage texture slot rules.

Первая версия должна быть рассчитана на **один основной mesh/rig model**.

Допускается анализ skeleton/bones, если он нужен для валидности custom runtime и будущих анимаций, но skeleton naming не должен проверяться по Lineage-справочнику.

---

## 14. Минимальный Character manifest

Рекомендуемый baseline:

```json
{
  "schemaVersion": 1,
  "project": "game1",
  "archetypes": [
    {
      "id": "default",
      "displayName": "Default Character",
      "serverStorageName": "DefaultCharacter",
      "sourcePath": "...",
      "preparedPath": "...",
      "sha256": "...",
      "modelAssetId": null,
      "status": "LOCAL",
      "revision": 1
    }
  ]
}
```

Дополнительные skeleton metadata могут быть добавлены как технические поля, но не должны становиться Lineage taxonomy.

---

# ЭТАП 5 — ВРЕМЕННЫЙ FIGHTER PLACEHOLDER

## 15. FFighter как bootstrap-заглушка

До регистрации первой настоящей модели нового проекта использовать уже опубликованную модель FFighter из RobloxLineage как **временный runtime placeholder**.

Критическое правило:

> FFighter не считается зарегистрированным ассетом новой базы на момент чистого старта.

То есть при первом запуске:

```text
Characters registered in Asset Manager: 0
```

При этом runtime уже может спавнить FFighter для проверки:

- character assembly;
- camera;
- movement;
- attack;
- HP/damage;
- hit/reaction pipeline.

Bootstrap placeholder должен подключаться через отдельный временный config/binding, а не через импорт старого `character-archetypes.json`.

Запрещено ради FFighter переносить:

- race/class/sex schema;
- FFighter-specific Asset Manager validation;
- Lineage texture slots;
- Lineage animation database;
- весь старый Character manifest.

После появления первой штатно зарегистрированной модели bootstrap fallback должен быть отключаемым и впоследствии удалён.

---

# ЭТАП 6 — CHARACTER RUNTIME

## 16. Custom character architecture

Сохранить проверенную схему custom character без Humanoid:

```text
Character Model
  RootCollider
  NavigationRoot
  ControllerManager
    GroundController
    AirController
  GroundSensorPart
    ControllerPartSensor
  Visual
    AnimationController
      Animator
```

Основной gameplay anchor — `RootCollider`.

World collision / locomotion должен оставаться отделён от визуальной модели.

Visual model:

- не определяет gameplay HP;
- не является источником authoritative position;
- не должен содержать Humanoid как обязательную основу;
- может быть заменён без переписывания gameplay state.

---

# ЭТАП 7 — КАМЕРА И ПЕРЕМЕЩЕНИЕ

## 17. Камера

Перенести текущую scripted-camera модель поведения RobloxLineage после переименования namespace и удаления лишних зависимостей.

На старте сохранить текущее ощущение управления:

- RMB orbit;
- mouse yaw/pitch;
- zoom wheel;
- min/max distance;
- collision raycast;
- camera target относительно `RootCollider`;
- frame-rate-independent smoothing rotation;
- `CameraType = Scriptable`.

Стартовые значения можно перенести из текущего рабочего runtime:

```text
target height: 5.5
distance: 10
min distance: 4
max distance: 18
FOV: 70
```

Эти значения являются начальными tuning values нового проекта, а не частью Lineage specification.

---

## 18. Перемещение

Перенести custom movement на базе `ControllerManager`.

Сохранить:

- WASD / arrows;
- camera-relative direction;
- jump;
- ground/air controller;
- `RootCollider`;
- `NavigationRoot`;
- ground sensor;
- поворот персонажа;
- существующую механику movement/facing locks, если она нужна атаке.

Убрать:

- lookup скорости по Lineage race/class;
- Lineage world-scale conversion;
- dependency на старый `CharacterMovementConfig` как базу расовых скоростей.

В новом проекте должна быть одна нейтральная стартовая movement profile.

Числовую скорость движения на первом этапе взять из текущего рабочего baseline, но записать как обычную настройку `DefaultMovement`, а не как параметр конкретного архетипа Lineage.

---

# ЭТАП 8 — НОВАЯ СИСТЕМА СТАТОВ

## 19. Базовые статы персонажа

На старте каждый персонаж имеет:

```text
Level   = 1
MaxHP   = 100
HP      = 100
Damage  = 10
Defense = 0
```

Это новая модель нового проекта.

Не переносить:

- CP;
- STR;
- DEX;
- CON;
- P.Atk;
- P.Def;
- M.Atk;
- M.Def;
- Combat V2 snapshots;
- Interlude class stat tables;
- level curves Lineage.

---

## 20. Формула урона

Defense блокирует урон линейно, единица в единицу.

Baseline:

```text
RawDamage   = Attacker.Damage
Blocked     = Defender.Defense
FinalDamage = max(0, RawDamage - Blocked)
NewHP       = max(0, CurrentHP - FinalDamage)
```

Примеры:

```text
Damage 10, Defense 0  -> 10 damage
Damage 10, Defense 3  -> 7 damage
Damage 10, Defense 10 -> 0 damage
Damage 10, Defense 20 -> 0 damage
```

На baseline нет minimum-1-damage rule.

Defense не является процентом.

---

## 21. Authority

Stats и damage должны быть server-authoritative.

Клиент:

- отправляет attack intent;
- показывает animation/VFX/UI feedback;
- не определяет итоговый damage;
- не изменяет HP самостоятельно.

Сервер:

- валидирует атаку;
- получает stats;
- рассчитывает `FinalDamage`;
- применяет HP;
- определяет death/alive state;
- реплицирует результат клиентам.

---

# ЭТАП 9 — ATTACK SYSTEM

## 22. Перенос атаки

Сохранить существующий пользовательский flow атаки RobloxLineage настолько, насколько он универсален:

- primary attack на LMB;
- attack intent;
- target/aim flow;
- range validation;
- attack timing/state;
- server authority;
- damage application;
- hit feedback;
- movement/facing lock integration.

Не переносить как обязательные части:

- Combat V2 database;
- Lineage weapon group rules;
- class/profession modifiers;
- Interlude skill mechanics;
- weapon-specific source tables;
- STR/DEX formulas.

На первом этапе attack должен работать и без Weapon subsystem.

Источником базового physical damage является:

```text
CharacterStats.Damage = 10
```

---

# ЭТАП 10 — INPUT

## 23. Стартовые input bindings

Сохранить общий принцип централизованных bindings.

Минимум:

```text
W / Up       — forward
S / Down     — backward
A / Left     — left
D / Right    — right
Space        — jump
RMB          — camera orbit
Mouse Wheel  — zoom
LMB          — primary attack
```

Остальные bindings добавлять только вместе с соответствующей feature.

Не переносить заранее quest journal, skill slots и другие несуществующие системы нового проекта.

---

# ЭТАП 11 — VERIFY / BACKUP / RECOVERY

## 24. Минимальный Verify

С первого этапа должны существовать автоматические проверки:

1. Rojo project корректен.
2. Проект не содержит runtime dependency на путь RobloxLineage.
3. Новый Docker/ports не конфликтуют с RobloxLineage.
4. Asset Manager Character manifest имеет правильную project identity.
5. Чистая база может содержать `0` registered characters.
6. Bootstrap FFighter может спавниться при `0` registered characters.
7. Camera binds к `RootCollider`.
8. Movement binds к `ControllerManager`.
9. Server-authoritative stats существуют.
10. Damage formula соответствует `max(0, Damage - Defense)`.
11. Новый проект не читает Interlude databases.
12. Новый проект не импортирует RobloxLineage manifests.
13. Backup/snapshot пишет только в новый project namespace.

---

## 25. Backup / DR

Сохранить принцип RobloxLineage:

> всё необходимое проекту должно быть либо локально recoverable, либо иметь проверенный путь восстановления.

Но новый recovery inventory формируется с нуля.

Никакие old-project assets автоматически не считать собственностью нового проекта.

FFighter bootstrap должен быть явно помечен как временная внешняя зависимость/placeholder, пока он используется.

---

# ЭТАП 12 — ПОРЯДОК РЕАЛИЗАЦИИ

## 26. Рекомендуемый порядок

### Шаг 1
Создать новый repository/root и базовые config-файлы.

### Шаг 2
Настроить Rokit + Rojo + чистый Place.

### Шаг 3
Поднять отдельный Control Center / host agent / Docker namespace.

### Шаг 4
Создать пустой Asset Manager shell без старых content sections.

### Шаг 5
Создать новый Character section и пустой `character-archetypes.json`.

Ожидаемое состояние:

```text
registered characters = 0
```

### Шаг 6
Подключить FFighter как временный bootstrap runtime model вне Character manifest.

### Шаг 7
Перенести и очистить custom CharacterService/runtime assembly.

### Шаг 8
Перенести CameraController.

### Шаг 9
Перенести MovementController и заменить Lineage movement profile на generic default.

### Шаг 10
Ввести новый `CharacterStats` contract:

```text
Level 1
HP 100
Damage 10
Defense 0
```

### Шаг 11
Перенести generic attack flow и подключить новую damage formula.

### Шаг 12
Добавить verify tests.

### Шаг 13
Проверить одновременный запуск RobloxLineage и нового проекта.

### Шаг 14
После стабильного baseline начать следующую отдельную миграцию Asset Manager section.

---

# 27. Definition of Done первого milestone

Первый milestone считается завершённым, если одновременно выполняются все условия:

- новый проект запускается из отдельной директории;
- Rojo live-sync работает;
- RobloxLineage при этом может работать параллельно;
- Docker/Control Center нового проекта полностью отдельный;
- persistent data/database отдельные;
- Asset Manager открывается;
- в Asset Manager существует только раздел Characters;
- Character database стартует пустой;
- можно создать новый Character Archetype без race/class/sex;
- archetype принимает одну character model;
- при пустой базе runtime использует bootstrap FFighter;
- игрок спавнится custom character runtime без стандартного Humanoid character flow;
- камера работает как в текущем RobloxLineage baseline;
- перемещение работает как в текущем baseline;
- LMB запускает базовую атаку;
- сервер хранит Level/HP/Damage/Defense;
- стартовые значения: `1 / 100 / 10 / 0`;
- Defense блокирует Damage 1:1;
- при HP = 0 персонаж считается мёртвым;
- ни одна gameplay formula не зависит от Interlude;
- ни один Asset Manager workflow не читает базы RobloxLineage;
- verification подтверждает отсутствие запрещённых cross-project dependencies.

---

# 28. Главное архитектурное правило на будущее

Новый проект наследует от RobloxLineage **способ ведения проекта**, но не его предметную модель.

То есть мы сохраняем:

```text
source -> validation -> manifest/state -> publication -> generated runtime -> verify -> backup/recovery
```

Но содержимое каждого нового раздела проектируется заново под новую игру.

Каждая следующая миграция — Characters, Animations, Weapons, Armor, Monsters, NPC и т. д. — должна быть отдельной задачей и не должна автоматически переносить Lineage-specific contracts.

---

# 29. Короткая формула проекта

> **Новый Place = чистая независимая игра + инфраструктурные принципы RobloxLineage + новый data model + постепенная миграция только нужных инструментов.**

Никакой зависимости нового проекта от Lineage II как источника истины быть не должно.
