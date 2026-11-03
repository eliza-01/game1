# M204 — визуальные MeshPart дома и timeline зарегистрированных атак

## Размещение Real Estate

`StudioRealEstateCollisionPolicy.Apply` — единственный writer физических флагов
MeshPart, вызываемый как полным Studio Sync, так и targeted part sync и refresh
ранее размещённых моделей. Все **визуальные** MeshPart (`house`, `door`,
`window_frames_glass`, `restoration` и будущие части) получают:

- `CanCollide = false`, `CanTouch = false`, `CanQuery = false`;
- `CollisionFidelity = Box`, `DoubleSided = true`.

Исключение: независимые `COL_*` / `*_col_*` / `*_col` — физические меши.
Им сохраняется отдельная collision policy, настройка `noCollide`, прозрачность,
тег `Game1RealEstateCollider` и `PreciseConvexDecomposition`. Ставить визуальным
мешам `CanQuery=true` ради оружия **нельзя**: это вернёт контакт оружия с
декорацией вместо COL_*.

Настройки `noCollide` для визуальных частей в старых Real Estate recipes
остаются как авторские метаданные, но **не управляют** физикой визуального
MeshPart при Studio Sync. Точка истины для физики — `COL_*`.

При первом применении M204 нужно выполнить обычный **Full Studio Sync**
для уже размещённых домов: без синхронизации старые модели в Workspace не
меняют сохранённые Roblox-свойства автоматически.

## Character attack timelines

`__` — намеренный разделитель полей ID. Менять его на `_` нельзя:
источники `assets/manifests/character-animations.json`, runtime registry и
`AttackTimelineData.luau` используют именно double-underscore.

В исходной базе отсутствовали четыре уже опубликованных таймлайна:
`human_male__weapon__1hs__attack__01/02/03` и
`human_male__weapon__hands__attack__01`.

- Длительности восстановлены из `assets/authoring/animations/human_male/*.animation.json`:
  1.5, 1.5, 44/30 и 1.5 секунды соответственно.
- **Временные** `HitStart=40%`, `HitEnd=50%` взяты как начальный шаблон из
  имеющихся `human_female__weapon__1hs__attack__02/03`.
- Все четыре записи отмечены `reviewRequired: true`. В Timeline UI показываются
  как `preset · review timing`, а не как подтверждённые/настроенные клипы.
  При явном Save из Timeline Editor флаг снимается автоматически.
- Runtime Lua экспортируется только из манифеста через `TimelineStore.export_runtime()`.
  Существующие публикации/Asset IDs и сами animation-клипы не изменяются.

**Важно:** до ручной настройки эти начальные проценты будут управлять окном
урона в Play. Это не извлечённые из анимаций события; их необходимо проверить
по фактической атакующей фазе через Timeline Editor. Если нужны полностью
безопасные, не действующие до проверки окна, надо отдельно вводить режим
`unapproved timeline` в клиентском и серверном бою — M204 его не вводит.

## Проверка

1. Выполнить Full Studio Sync для дома, проверить визуальные MeshPart и
   независимый физический `COL_*`. Проверить дверь, проходы, HouseSocket F,
   луч оружия и GroundSensor (CanQuery на визуалах отключён).
2. Выполнить Play с `human_male`, сменить 1hs атаки 01–03 и hands 01,
   убедиться в отсутствии `attack clip has no timeline`. При отсутствии
   игровой публикации анимации проблема может быть связана с другими ошибками.
3. В Control Center → Timelines последовательно открыть четыре клипа,
   выставить фактические HitStart/HitEnd и нажать Save.

Проверки Python/статических контрактов не заменяют Roblox Studio Play.
