# M90 — первый этап декомпозиции MonsterSpawnerService

Основа: M89. Область изменений: `src/server/monster`, проверки `system/verify`. Схема SQLite, манифесты, HTTP API, Studio Bridge, AI и RemoteEvent не меняются.

## Границы ответственности

| Модуль | Владеет | Не владеет |
| --- | --- | --- |
| `MonsterSpawnerService` | Оркестрация спавна, популяция, таймеры, блуждание, переходы анимационных состояний, смерть и респавн | Создание физического рига, выбор точки на земле, декодирование слотов клипов, начальные атрибуты |
| `MonsterRigBuilder` | Подготовка визуальной модели, нейтральный RootBone, GroundAlign, NavigationRoot/RootCollider/Humanoid | AI, анимационные события, урон, популяция |
| `MonsterSpawnGeometry` | Выбор случайной точки в круге, raycast поверхности, выбор блуждающей цели и горизонтальная дистанция | Собственный RNG, самовольное создание папки, AI |
| `MonsterAnimationTrackFactory` | Отбор опубликованных клипов, загрузка штатных AnimationTrack, fallback слотов и приоритетов, конструирование треков для entry | `Play/Stop`, тайминг idle_special, death, состояние боя |
| `MonsterInitialAttributes` | Чтение параметров published definition и начальная установка runtime-атрибутов | Бой, сетевые события, физика, регистры/БД |

## Совместимость

* У `MonsterSpawnerService.Start()` тот же контракт и bootstrap-зависимости.
* **Тот же `spawnRandom`** передается в `MonsterSpawnGeometry`; вызовы `NextNumber` и `NextInteger` остались на прежних этапах. Выбор `idle_special` использует тот же RNG.
* Внутренняя raycast-политика не меняется: исходные высоты 96/384, `RespectCanCollide=false`, папка `Workspace.Monsters` исключена из запроса.
* Выравнивание к земле, RootBone, единственный weld к визуальному корню, навигационный Humanoid и коллайдер не меняются.
* Порядок: клонирование → подготовка visual → RootBone → координата/yaw → GroundAlign → атрибуты → navigation rig → hitbox → native animation tracks → подписки → idle → wander.
* Слоты анимаций и fallback `combat_idle→idle`, `walk↔run` не меняются; death по-прежнему одноразовый.
* Не вводятся новые постоянные циклы, RemoteEvent, кеши моделей или глобальные состояния.
* Миграции данных не требуются, файлов ассетов и Roblox Animation ID нет в diff.

## Проверки

1. `python system/verify/verify.py`
2. `python -W error::ResourceWarning -m unittest discover -s system/verify -p 'test_*.py' -q`
3. `git apply --check` к дереву после M89.
4. **Обязательно в Roblox Studio Play (сервер):** разместить минимум один действующий spawn монстра и проверить:
   - появление с правильной высотой/поворотом/коллизиями, `CombatHitboxCount`;
   - idle + idle_special, паузы и блуждание внутри authored radius;
   - начало боя, Chase/Attack и возврат к обычному состоянию;
   - получение смертельного урона, death terminal hold, утопление трупа и респавн с `maxAlive`;
   - изменение RunSpeed и MonsterLocomotionMode через Debug при блуждании.

Статические Python-проверки **не воспроизводят физику Roblox, Animator или PreAnimation**. Если активных `MonsterSpawnRegistry.records` нет, зелёный запуск Play не проверяет эти ветви; для проверки нужен хотя бы один тестовый monster spawn.

## Следующий шаг

M91: вынести state machine блуждания/locomotion и смерть/респавн в отдельные сервисы с явным lifecycle cleanup, а `MonsterSpawnerService` оставить владельцем популяции. Делать отдельно от изменений поведения боёвки.
