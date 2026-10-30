# game1 — действующая карта архитектуры

**Аудит по коду:** 30 октября 2026, `game1_diag_2026-10-30_13-52-46.zip`, после M162.
**Источник инженерных ограничений:** [`AGENTS.md`](../../AGENTS.md).
**Историческое обоснование:** [аудит 14 октября](../ARCHITECTURE_AUDIT_2026-10-14_RU.md). Его старые размеры файлов и список «следующих этапов» не актуальны.

## Слои и направления зависимостей

```text
Blender/FBX, atlas files
      ↓
system/asset-manager/ + system/control-center/{api,services,stores,real_estate}
      ↓          ↘ Open Cloud / local Host Agent / SQLite
assets/manifests + src/shared registry exports
      ↓
system/studio-plugin/ modules  →  Studio templates / placed models
      ↓
src/shared {contracts, policies, calculations, registries}
      ↙                                        ↘
src/server {authority, actors, house, combat}   src/client {input, presentation, debug}
```

Studio Plugin/Host Agent — **authoring plane**, не клиентский игровой runtime. Реплицируемые RemoteEvents не становятся источником истины о положении, владении предметом или уроне.

## Фактически выделенные компоненты

| Направление | Текущая граница | Проверено в исходниках |
| --- | --- | --- |
| Server bootstrap | `src/server/bootstrap/ServiceCatalog.luau`, `ServiceBootstrap.luau` | Список критичных/необязательных сервисов, dependencies, startup health; `init.server.luau` — тонкий entrypoint |
| HTTP Agent | `system/control-center/host_agent.py`, `api/read_dispatch.py`, `api/write_dispatch.py` | Роутинг вынесен; конструирование stores и dependency wiring всё ещё централизованы |
| Monster runtime | `src/server/monster/MonsterSpawnerService.luau`, `MonsterAIService.luau` и узкие modules | Population/AI/navigation/attack/lifecycle выделены; их не следует собирать обратно в один сервис |
| Combat | `src/server/combat/AttackService.luau`, `EntityHitboxService.luau`, spatial/session modules | Server authority, attack session и hitbox geometry разделены частично |
| Studio Bridge | `system/studio-plugin/Game1Bridge.server.luau`, `modules/Studio*` | Команды, Timeline, scene placement, Real Estate и validation разделены |
| Real Estate | `system/control-center/real_estate/{store,contracts,studio_sync,jobs,...}.py`, StudioRealEstate* | Авторинг и mesh revisions отдельно от sync; `store.py` всё ещё крупный |
| FBX | `system/asset-manager/model_publication.py`, `bone_weight_survival.py` | Общая подготовка скиннинга; независимо от ассетной категории, включая проверку покрытия вершин |
| Atlas | Registry + consumers Location/Real Estate | Shared Image ID у варианта; legacy inheritance поддерживается для существующих записей |
| Verification (M164–M170) | `system/verify/verify.py` → `system/verify/validators/` | Вынесены source-only, project layout, Monster registry/spawn, Actor runtime и Combat Contact/Headshot, Character, Animation, Weapon, Studio Debug, Death, Attack Timeline и Rojo/Animation Speed tooling, Location/Deco/Environment/Texture Sync (M169), Combat foundation/Hitbox/Studio Character Bridge/registered attack clips (M170). `verify.py` содержит только orchestration, сохранены CLI и порядок ошибок; финальная обработка M54/M55 ещё открыта |
| House runtime | `HouseSocketContract`, `HouseElevatorPolicy`, `HouseSocketService`, `HouseDoorService`, `HousePadlockService`, клиентский Prompt, Studio debug | USE/AIM, модельный pivot двери, server authorization; детальнее в [ТЗ](../spec/CURRENT_PROJECT_SPEC_RU.md) |

## Опасные устаревшие предположения

- **Не считать** `StudioRealEstateSocketRecovery` действующим механизмом: M133 описывает удалённый в M153 workaround. Текущий Studio Bridge проверяет фактические Bones.
- **Не считать** `M146` текущими клавишами: единая `F`-подсказка заменена более поздними M155/M159/M161 правилами.
- **Не считать** AIM зоной курсора на экране: после M161 луч идёт из центра прицела, проверяется occlusion. Старые описания M160 — снимок предыдущей реализации.
- **Не считать** `TextureID` у каждого потребителя отдельной независимой публикацией: M125/M162 используют Atlas Registry и адаптеры наследования.
- **Не делать** реставрацию автора в Studio при потере костей и не вводить компенсационное масштабирование Model без сравнения Blender/FBX/Roblox.
- **Не обобщать** «завершено» на всё MMO: в коде есть placeholder chest/lock/key, а опубликованные ID и приватные данные вне dump не переоцениваются.

## Зоны ответственности, ещё требующие декомпозиции

Текущие размеры: `verify.py` **187 строк после M170** (2986 до M164), `MovementDebugController` ~1009, `TestLoadoutController` ~987, `monster_animation_store.py` 946, `real_estate/store.py` 822, `character_store.py` 806, `location_asset_store.py` 691 строк. **Размер лишь триггер аудита, не доказательство неправильных границ.** Для каждого этапа нужен анализ read/write ownership, API и тестов.

- Python stores: хранение + публикационный workflow + совместимость legacy/manifest могут смешиваться; выносить через service/repository с сохранением внешних методов.
- Клиентские debug UI: повторяющиеся элементы и управление inputs, но не выносить gameplay ownership из server.
- NPC на monster-инфраструктуре: это существующая внутренняя совместимость, не контракт будущего `Actor` API.
- `HouseSocketService` и большой debug controller: дополнительно распределять state, eligibility, effect и UI при росте функционала.
- `verify.py`: M164–M170 вынесли 23 валидатора (source-only, project layout, Monster, Actor runtime, Combat Contact/Headshot, Character, Animation, Weapon, Studio Debug, Death, Attack Timeline и authoring tooling, Location authoring, Location Assets, Deco Studio, shared texture variants, environment bounce, published texture sync, categories). Фасад уже стал тонким координатором; дальнейшего дробления ради количества строк не требуется. Сохранять CLI, ошибки и тесты. Известный дефект прежнего CLI: M54/M55 стоят после промежуточного `if errors`, поэтому их ошибки не переводят exit code в 1; исправлять отдельно после завершения behavior-preserving экстракции.

## Статус первоначального рефакторинга

M85–M105 **реализовали** значительную декомпозицию bootstrap, Host Agent, Monster lifecycle, Combat/Hitbox и Bridge. До M162 появились другие доменные модули. Старый текст `Planned decomposition (not yet implemented)` в AGENTS был устаревшим. Нынешний список и последовательность с критериями — [REFACTOR_ROADMAP_RU.md](REFACTOR_ROADMAP_RU.md).

## Порядок обновления этой карты

При изменении сервиса, store, контрактов Remote или schema обновлять: (1) текущую карту/ТЗ, (2) область проверки и ограничения, (3) исторический milestone-отчёт при крупном изменении. Не переписывать задним числом старые выводы. Наличие README или unit test не равно авторскому подтверждению Studio runtime.
