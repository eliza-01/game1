# GAME1 — отчёт по реализации M1

## Реализовано

- новый независимый project identity `game1`;
- отдельные Rojo namespaces: `Game1Shared`, `Game1Server`, `Game1Client`;
- `CharacterAutoLoads = false` и custom character runtime;
- Rokit + Rojo 7.7.0;
- отдельные порты: Control Center `43820`, host agent `43821`, Rojo `34882`, reserved Studio bridge `43137`;
- отдельный Docker Compose project/container/network;
- отдельная SQLite база `.control-center/game1.db`;
- чистая Character DB: 0 зарегистрированных archetype на baseline;
- Asset Manager только с разделом Characters;
- один archetype = один model source / один Roblox Model Asset ID;
- ingest локального model source в `assets/source/characters/<id>/model/` с SHA-256;
- deterministic export SQLite -> JSON manifest -> Luau CharacterRegistry;
- FFighter asset `99674249877653` только как bootstrap fallback и не как запись новой базы;
- custom character: `RootCollider + NavigationRoot + ControllerManager + Ground/Air controllers + Visual`;
- scripted camera, перенесённая из проверенного runtime и отвязанная от старого namespace;
- camera-relative movement, walk/run, jump и movement/facing locks;
- новые stats: Level 1, MaxHP/HP 100, Damage 10, Defense 0;
- server-authoritative melee attack;
- формула `FinalDamage = max(0, Damage - Defense)`;
- Studio-only training dummy для быстрой проверки damage flow;
- HUD с Level / HP / Damage / Defense;
- Rojo Studio plugin installer;
- отдельный минимальный `Game1Bridge` Studio plugin;
- build script для чистого `place/game1.rbxl`;
- verify script для project identity, forbidden cross-project dependencies, ports и damage contract;
- project snapshot script.

## Safety boundary Place-файла

После уточнения project identity канонический Place закреплён как `place/game1.rbxl`. Имя `current.rbxl` в game1 запрещено: bootstrap/build/verify останавливаются, если `place/current.rbxl` появился в новом проекте. Это сделано специально, чтобы не открыть и не перезаписать `RobloxLineage/place/current.rbxl` по привычке.

`bootstrap.ps1` также отказывается запускаться из пути, содержащего `RobloxLineage`; game1 должен лежать отдельной sibling-директорией.

## Проверено в текущей среде

- Python syntax Control Center/verify;
- SQLite initialization;
- Character CRUD;
- source ingest + SHA-256;
- JSON manifest export;
- Luau CharacterRegistry generation;
- возврат базы в 0 registered characters после теста;
- host-agent HTTP API;
- web Control Center -> host-agent proxy;
- static forbidden-coupling scan;
- отсутствие конфликтов с известными портами RobloxLineage.

## Не проверено автоматически в текущей среде

В среде сборки отсутствуют executables `rojo`, `rokit` и `docker`, поэтому здесь нельзя было реально выполнить:

- `rojo build`;
- Rojo Studio plugin install;
- сборку `place/game1.rbxl`;
- Docker Compose build/up;
- Play-тест Roblox Studio;
- фактическую загрузку model asset `99674249877653` через `InsertService.LoadAsset` внутри Studio.

Для этого предусмотрен `bootstrap.ps1`, который запускает эти проверки/сборки уже на Windows-машине проекта.

## Важная граница M1

Это не перенос полного combat stack RobloxLineage. Сохранены control/runtime contracts камеры, движения и server-authoritative атаки, но Lineage Combat V2, weapon DB, animation DB и прочие предметные зависимости намеренно отсутствуют. Дальнейшие разделы Asset Manager мигрируются отдельно.
