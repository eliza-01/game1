# NPC subsystem · M59 (1hs)

## Границы ответственности

- **Asset Manager / authoring**: `host_agent.py` и отдельные UI-файлы `npc-assets.js`, `npc-spawns.js`; NPC публикуются через уже существующий Open Cloud pipeline. Их записи хранятся в `.control-center/game1_npcs.db` и не смешиваются с монстрами/персонажами.
- **Published contracts**: `assets/manifests/npcs.json`, `npc-animations.json`, `npc-spawns.json`; экспортируются в `NpcRegistry`, `NpcAnimationRegistry`, `NpcSpawnRegistry`. Сервер использует эти read-only регистры, не обращается к HTTP/SQLite.
- **Studio authoring**: общий транспорт `studio_bridge.py`; команды размечены `entityKind=npc`. Маркеры располагаются отдельно в `Workspace.Game1Authoring.NpcSpawns`. NPC-ассеты — в `ServerStorage.npcs.<slug>.model.<slug>`. Обновление допускается только для шаблонов с `Game1NpcRig=true`.
- **Spawner**: `NpcSpawnerService` авторитетно управляет популяцией (`maxAlive`, `spawnRadius`, `placeId`, `respawnSeconds`). Возрождение начинается после исчезновения тела, и не превышает локальный лимит. Каждый экземпляр существует только на сервере и имеет уникальный runtime identity.
- **Presentation**: `NpcRigFactory` отвечает за визуальную сборку, `NpcAnimationService` — за анимационный lifecycle. Спавнеру неизвестны детали костей и треков.
- **Combat**: общий `EntityHitboxService` + `DamageService` определяют попадания и HP; NPC имеют `NpcSlug`, `Damageable`, `LifeState`, `HP`, `MaxHP`. После `Dying` используется общий `DeathLifecycleService`. NPC никогда не регистрируются в агро/AI монстров.

## Контракт первой итерации

Только профиль оружия `1hs`: `idle`, `idle_special_01..n`, `walk`, `run`, `combat_idle`, `attack_01..n`, `death`. Для постановки NPC на точку требуется опубликованная модель (и доступный в Studio шаблон); `idle` и `death` **не обязательны**. Отсутствующие анимации отображаются в Asset Manager как предупреждение, но не блокируют создание и валидацию спавна. Без `idle` NPC стоит в базовой позе рига, без `death` смерть завершается без проигрывания клипа. Требования к анимациям монстров остаются прежними. Остальные слоты можно зарегистрировать/опубликовать сейчас, но они будут использоваться будущим отдельным NPC movement/AI компонентом. NPC статичны, пассивны, уязвимы для атак игроков, умирают, исчезают и возрождаются. Квесты, торговля, диалоги, дружелюбные/враждебные фракции и активные атаки NPC в M59 **не реализованы**.

## Важные инварианты

1. `npcs.db` не содержит записей Monster DB; `assets/source/npcs` — отдельный источник FBX.
2. Отдельные `NpcSlug`/`Game1NpcRig`; никакой `MonsterSlug` на NPC runtime. Внутренние поля serialized spawn store (`monsterSlug`) сохранены ради повторного использования существующего валидатора и транспортного контракта; не означают тип сущности.
3. Никакая авторская точка не порождает модель, пока шаблон не опубликован и не скопирован в Studio. Для обновления опубликованного FBX создаётся новый Roblox Asset ID.
4. Studio Plugin необходимо пересобрать и перезапустить Studio после M59, но **Rojo-сервер не нужно перезапускать**.
5. Проверки без Studio: `python system/verify/verify.py` + `python system/verify/test_npc_pipeline.py`. Отдельно проверять runtime в Studio: регистрацию, FBX/анимации, marker sync, получаемый урон, позу смерти, удаление тела и количество NPC после respawn.

## M62 · Размещение NPC с предпросмотром

- Host Agent синхронизирует опубликованный rig NPC с `ServerStorage.npcs.<slug>.model.<slug>` **до** входа в режим размещения. Без опубликованного rig режим не запускается. Анимации по-прежнему необязательны.
- `NpcSpawnPreview` (только плагин Studio) создаёт небоевую, полупрозрачную копию rig в черновом marker. Не создаёт `NavigationRoot` runtime, не использует `DamageService`, не меняет NPC реестр.
- `NpcSpawnPlacement` (только плагин Studio) управляет жестом: наведение — позиция на физической поверхности; удержание ЛКМ — блокировка позиции и вращение горизонтальным drag; отпускание — подтверждение; Esc — отмена и удаление preview.
- После отпускания предварительная модель остаётся в черновой точке до `register`. При регистрации marker заменяется лёгким маркером без копии тяжёлой модели, чтобы количество NPC spawn points не раздувало `.rbxl`. В Play режиме runtime использует те же `position` и `yawDegrees`.
- Монстры используют старый `monsterSpawnPlacementResult` без изменений; направление NPC читается из того же поля `yawDegrees` в общем spawn contract.

## M63 · Анимационное состояние NPC и веса idle

- `NpcAnimationTracks` — адаптер опубликованных `NpcAnimationRegistry` rows для профиля оружия из `NpcAnimationConfig`. Создаёт `AnimationTrack`, управляет приоритетами, скоростью и optional runtime-only `AnimationFirstFrameSeam`. Не знает про боевые состояния или популяцию.
- `NpcIdlePresentation` — самостоятельный контроллер мирного idle. Идентифицирует base/special по `role`/`sourceSlot`, выбирает варианты из весов через общий `WeightedAnimationChoice`, запускает special на границе завершения base idle и возвращается к base после special. Для base с включённым `first→end` граница определяется seam; иначе — `DidLoop`. При отсутствии работающего base idle выбор выполняется с интервалом `MissingBaseIdleCycleSeconds`.
- `NpcAnimationService` — оркестрация состояний `idle ↔ combat_idle → death`. Переход в бой и смерть останавливает special, смерть управляется `DeathAnimationPolicy`; сервис предоставляет `Step`/`Destroy` и не создаёт/не удаляет NPC.
- `NpcSpawnerService` владеет экземплярами NPC и вызывает `presentation.Step` до завершения жизни, а `presentation.Destroy` при очистке. Без AI NPC не атакуют.
- Веса NPC от `0` до `10000`. Значение `0` исключает вариант из выбора. Веса пропорциональны: при base=300, special_01=25 и special_02=0 вероятность special_01 при очередном выборе равна `25/(300+25)`; special_02 не выбирается. Существующая шкала monsters (`1..10000`) не изменяется.
- Для диагностики в Roblox Studio у NPC выставляется атрибут `NpcIdleVariant` = `base` / `special_XX` / `nil`; `NpcAnimationState` остаётся `idle`, `combat_idle` или `death`.
- Модули не содержат имён NPC и не зависят от структуры отдельного реестра конкретного персонажа. Не опубликованные анимации не загружаются. Для корректной демонстрации надо проверить игру непосредственно в Roblox Studio: модель со связанным FBX-скелетом и опубликованные `idle`, `idle_special_01`.

## M64 · Канонический скелет NPC при спавне

- `NpcRigFactory` не создаёт искусственный `RootBone` и не переподчиняет опубликованные кости. Исходная иерархия (`spine`, ветви рук и ног и т. д.) является частью контракта FBX/Roblox-анимаций и должна сохраняться при клонировании любого NPC.
- `NavigationRoot`, `RootCollider` и weld-соединения отвечают за положение и игровые столкновения; они не должны быть родителями скелетных `Bone` и не должны менять `Bone.Transform`.
- `NpcSpawnerService` сначала собирает NPC через `NpcRigFactory.Create`, затем вызывает `NpcAnimationService.Create`: `Animator` привязывается к уже окончательной иерархии костей. Временные runtime-скрипты, пересоздающие `Animator` после спавна, не нужны.
- Исправление относится ко всем опубликованным NPC без привязки к `slug` или weapon set. Для имеющихся экземпляров требуется новый запуск Play (или обычный despawn/respawn), уже созданные в текущей симуляции кости автоматически не перестраиваются.
- Треки `idle`, взвешенные `idle_special`, `combat_idle` и `death` остаются под управлением `NpcAnimationService`, без принудительного зацикливания или повышенного приоритета.
- Монстры имеют отдельную реализацию runtime-рига; её поведение этим изменением не затрагивается.

## M65 · Бесшовный выход из NPC idle_special

- Одноразовый `idle_special` больше не ждёт `AnimationTrack.Ended`: событие приходит после fade-out и оставляло окно без активной позы между special и base idle.
- `NpcIdlePresentation.Step` в `PreAnimation` инициирует crossfade за `SpecialExitBlendSeconds` реальных секунд до завершения клипа. Скорость вычисляется по фактической скорости, которую `NpcAnimationTracks.Play` передал Animator.
- При возврате сначала запускается base idle, затем специальная анимация плавно затухает с той же длительностью; скелет не остаётся без весов. `Stopped` служит страховкой, если клип завершился раньше очередного шага.
- Не затрагиваются экспортированные ассеты, веса выбора idle, loop base idle, смерть, боевые состояния и строение рига. Для режима без базовой idle необходима отдельная политика удержания/переходов между специальными анимациями.
