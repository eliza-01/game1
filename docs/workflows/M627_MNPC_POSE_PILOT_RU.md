# M627 · MNPC Architecture & Presentation Separation — пилот

База: M626 + согласованный документационный патч MNPC. KBN-0037-T08/A07. Производственный Runtime не изменён; feature ещё не включена. Цель этапа — выбрать способ authoritative pose, который не заставит дальние клиенты вычислять анимацию. Это не benchmark и не тест с сотнями существ.

## 1. Карта владельцев и потребителей (аудит M626)

| Обязанность | Текущий producer → consumer | Контракт при разделении |
|---|---|---|
| Движение и физика | `MonsterRigBuilder`, `NpcRigFactory` → navigation Humanoid, HumanoidRootPart, RootCollider, `VisualRootWeld`; AI/NavigationScheduler | Сервер сохраняет root/collider/ownership, ориентацию, позицию и lifecycle. Клиентский mesh не участвует в physics/query. Не заменять actor root визуальным pivot. |
| Native pose | `MonsterAnimationTrackFactory`, `MonsterCombatPresentation`, `MonsterIdlePresentation`, `MonsterDeathLifecycle`; `NpcAnimationService`, `NpcAnimationTracks`, `NpcLocomotionPresentation`, `NpcIdlePresentation` → Animator в visual rig | Native binding использует имя и иерархию (см. `NpcAnimationRigBinding` и Monster RootBone bridge). Сохранить authored clips, priority, blend, speed, phase, weighted choice, death. Нельзя управлять server tracks от LOD наблюдателя. |
| Боевые объёмы | `EntityHitboxService.Attach` → `HitboxMeshGeometryCache`, `HitboxDefinitionBuilder` (MeshPart geometry/scale/path), binding anchors → `HitboxRuntimeFrames.Refresh` → `SkeletonHeadResolver.TransformedBoneFrame` → `HitboxSpatialQueries` | Одной замены MeshPart на Part при spawn недостаточно: Attach требует исходную геометрию. Сначала подготовить definition по FULL, затем проверенно привязать к authoritative bones/frames. Fallback RootCollider не считать эквивалентом head/body. Hitbox Precompute целиком не входит в M627. |
| Стрела | `BowHitscanService`, `ArrowSurfaceContact` → клиентский `BowShotVisualController` (nearestBone, sticking) | Серверные surface/headshot queries сохраняются; клиентский контакт должен разрешаться в текущий owned FULL rig, при unload освобождать follower/arrow. Не переносить старый Bone Instance между generations. |
| Экипировка | `NpcEquipmentService`, `WeaponEquipService`, `WeaponPresentationState` → socket Bone/RigidConstraint; `NpcWeaponVisibilityController` | Gameplay weapon state остаётся серверным; FULL локально воспроизводит socket binding и видимость. LOD1 — запечённый вариант, без отдельного оружия и волос. M609 контракт не менять. |
| Дополнительная локальная поза | `MonsterAttackLocomotionController`, `NpcAttackLocomotionController` → `ActorSamplerPool`, `ActorSkeletonMap`, `ActorLowerBodyPose` | Разрешать sampler только для текущего FULL visual; release lease при detach/LOD1/death/stream-out. Не менять серверную позу локальным Bone.Transform. |
| Spawn/death/эффекты | `MonsterSpawnPresentation`, `MonsterDeathLifecycle`, `DeathLifecycleService`, `StatusEffectVisuals`, `MonsterHomeRecallVisuals` | Spawn fade/rise и death phase должны стать явным presentation state; не воспроизводить их на каждом LOD1 и не менять Damageable/HP/despawn. |
| UI и discovery | `OverheadHealthController`, `NpcOverheadController`, `HealthBarView` используют Game1MonsterRuntime/Game1NpcRuntime, LifeState/HP/slug; target/interaction остаются на actor | UI следует текущему FULL, отдельно от root/HP. Не регистрировать визуальную копию как второго NPC/Monster. Цель и proximity остаются authoritative. |

## 2. Проверяемые варианты

- A: native Animator + технический носитель Bone hierarchy без skinned MeshPart в Workspace. Может сохранить authoritative pose, но Animator всё ещё реплицируется. Даже CARRIER_MATCH не доказывает нулевую клиентскую анимацию. Если клиент NONE получает playing tracks или видимое изменение Bone frames, A самостоятельно **не удовлетворяет ТЗ**.
- B: server-only native carrier. Roblox [Animator.LoadAnimation](https://create.roblox.com/docs/reference/engine/classes/Animator/LoadAnimation) документирует требование Workspace для LoadAnimation. Проверяем отдельно fresh load в ServerStorage и перемещение уже загруженного носителя туда. Возврат AnimationTrack не доказывает вычисление позы; нужен motion и эквивалентность authoritative frames. Не принимать неподвижный carrier как успех.
- C: если native private path не подтверждён, исследовать server-side sampling клипов/authoritative pose без реплицируемого Animator, с проверяемой поддержкой blend/easing/phase/priority/root motion и точностью head/body; FULL — локальный Animator по серверному snapshot. Не внедрять непроверенный evaluator, не упрощать боевые хитбоксы ради FPS. Решение следующего этапа фиксируется по engine evidence.

## 3. Изолированный эксперимент (реализация M627)

`MnpcPoseProbeService` / `MnpcPoseProbeController` и общий `MnpcPoseProbe`. Только явный вызов в Studio Play, никаких bootstrap registration, remotes, production callbacks, config migrations и изменений реальных actor. Из уже существующих Alive MNPC выбирается не более одного Monster и одного NPC с загруженным активным клипом (weight > 0.5). Пилот копирует только skinned mesh roots и Bone hierarchy, сохраняет имена/пути/rest CFrame, исключает scripts, tags, attributes, physics/query и gameplay state. Референс и plain carrier невидимы; все fixture Parts anchored, no collision/touch/query. Если структура неоднозначна или кости не скопировались целиком — INCONCLUSIVE, не частичный PASS. Тестовые модели Persistent для наблюдения, не решение для реального streaming.

Для одного клипа сравниваются mesh-local TransformedWorldCFrame всех Bones на 10/35/60/85% клипа (5 Heartbeats после выставления фазы). Порог сравнения пилота 0,01 stud / 0,5°; отсутствие изменения reference → INCONCLUSIVE_REFERENCE_STATIC; совпадение только на этих фазах → CARRIER_MATCH, не полная эквивалентность боевых поз. Отдельно PRIVATE_LOAD и MOVE_TO_PRIVATE, наблюдение 1,5 секунды; затем REPLICATED_CARRIER. Native track/controller reference удаляется, статический шаблон остаётся лишь на время пилота. NONE клиент не создаёт rig, FULL клиент вручную создаёт локальную копию и локальный Animator; обе копии невидимы, это измерение pose/ownership, не визуальная приёмка. NONE — ещё не настоящий LOD1 (нет опубликованного mesh). Локальный клип свободно играет, фазовая синхронизация с сервером в этом пилоте не реализована. Наблюдаются bone motion, count of meshes/animators/tracks, доступность EvaluationThrottled; отсутствие изменений за 2 сек не доказывает отсутствие CPU cost. При отсутствии живого активного источника SKIPPED_NO_ACTIVE_ACTOR. Результат JSON, автоматическая очистка fixtures через 60 секунд после серверных экспериментов (остановка Play также очищает всё). Клиентский visual удаляется после каждого наблюдения/ошибки. Не выполняется в опубликованной DEV игре.

## 4. Минимальный запуск

После Rojo sync и обычного Studio Play (когда NPC/монстры уже появились), переключить Command Bar на Server:

```lua
require(game.ServerScriptService.Game1Server.dev.MnpcPoseProbeService).Start()
```

Скопировать строки `[MNPC627][server]` из Output. Запуск сам завершает проверку; дополнительных действий с персонажем не требуется. Если активного клипа нет, дать существу начать обычное движение/idle и повторить после CLEANED. Если понадобится подтверждение клиентской стороны — в окно CLIENT_OBSERVATION_WINDOW, в клиентской Command Bar:

```lua
require(game.Players.LocalPlayer.PlayerScripts.Game1Client.dev.MnpcPoseProbeController).Observe("NONE")
```

На втором Studio клиенте при необходимости `Observe("FULL")` тем же require. Можно провести отдельно позднее; серверные результаты достаточны для выбора следующего диагностического шага, но не для закрытия A07. Если Output не содержит OBSERVED или модель не реплицировалась — повторять только при необходимости. Не требуется 200 объектов, profiler, публикация или телефон на данном этапе.

## 5. Статус и ограничения

Static audit и diagnostic implementation выполнены, engine experiment NOT_RUN в среде подготовки патча (нет Roblox Studio). Не заявляется уменьшение FPS/CPU, прекращение native animation evaluation или production LOD. Не начинать production migration до результата этого gate; если обе native гипотезы не подходят, уточнить C и договориться о контракте прежде чем менять gameplay. Следующий шаг после получения Output — выбор authoritative pose path; authoring MNPC и dynamic LOD остаются отдельными этапами. T08/A07 открыты.
