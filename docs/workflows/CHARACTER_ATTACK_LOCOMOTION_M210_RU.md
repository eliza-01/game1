# M210 · Character attack: live legs + upper-body composition

## Причина

У игровых персонажей давно есть `AttackUpperBodyComposer`: отдельный скрытый
`AnimationTrack` проигрывает полный атакующий клип, но в видимый скелет копируется
**только поддерево верхней части тела**. `CharacterAnimationController` оставляет
видимый Animator на `run`, `walk` или `combat_idle`. Система работала лишь при
условии, что Composer находит правильный мост позвоночника.

Старый поиск распознавал исключительно `spine.001`/`spine.N`. У `human_female`
скелет имеет `spine -> spine.001 -> spine.002`; у `human_male` —
`pelvis -> spine_01 -> spine_02 -> spine_03`. Поэтому male не находил мост,
а клиент автоматически проигрывал **полнотелую** атаку на видимом Animator:
ноги брались из неё, а не из бега. `AimPoseController` имел тот же устаревший поиск.

## Контракт M210

- `CharacterUpperBodyRig.ResolveBridge(visual)` определяет **второй сегмент
  непрерывной цепочки spine** по иерархии `Bone.Parent`. Ожидаемая кость для
  female — `spine.001`, для male — `spine_02`.
- Проверка не позволяет включить в атакуемое поддерево `pelvis`, `thigh`,
  `shin`, `foot` и прочие ветви ног. Неоднозначный/неполный скелет даёт ошибку,
  а не случайную маску.
- `AttackUpperBodyComposer` и `AimPoseController` используют один резолвер.
- Атакующий `AnimationTrack` больше **никогда** не проигрывается на видимом
  Animator как fallback. Если сборка невозможна, `PlayAction` возвращает nil,
  атака не отправляется на сервер, Output сообщает `attack ... cancelled`.
- Для каждого удара корректно обновляется слот ног в реальном времени:
  движение (`MovementState`) + профиль экипированного оружия → `run`/`walk`;
  остановка → `combat_idle`. Скорость бега продолжает определяться
  `WeaponAttackMovement`/`RunSpeed`, а общий период удара — M206.
- Асинхронная загрузка атакующего клипа защищена от повторного ввода,
  смерти и смены персонажа. Длительность gameplay-атаки стартует **после**
  готовности source-трека, не уменьшается на время первого LoadAnimation.
- Ни серверный урон, ни таймлайны `HitStart`/`HitEnd`, ни публикации анимаций
  не изменены. Системы Monster/NPC не затронуты.

## Диагностика в Play

На клиентском Model персонажа:

| Атрибут | Ожидаемое значение в атаке |
| --- | --- |
| `AnimationAttackUpperBodyComposed` | `true` |
| `AnimationAttackBridgeBone` | `spine_02` (male), `spine.001` (female) |
| `AnimationAttackLowerBodySlot` | `run`/`walk` при движении, `combat_idle` после остановки |
| `AnimationAttackCompositionError` | отсутствие значения после успешной атаки |

Проверка в Roblox Studio Play:

1. Запустить `human_male` с оружием 1HS, начать бежать и нажать атаку **не отпуская W**. Руки/торс играют удар, ноги продолжают бежать.
2. Во время длительной атаки отпустить W, а затем снова нажать: ноги должны переходить в `combat_idle` и обратно в `run` без прерывания верхнего удара.
3. Повторить с `human_female`, с `hands`, а также с движением назад и `walk`-профилем оружия.
4. Проверить, что при `AttackSpeed = 200` длительность атаки соответствует M206, а попадание ограничено её авторским таймлайном.
5. При ошибке `upper-body composition unavailable` проверить текст Output и `AnimationAttackCompositionError`. Полнотелый удар не должен маскировать эту ошибку.
6. При отмене атаки/смерти проверять отсутствие оставшихся в Workspace `__Game1AttackUpperBodyProxy`.

## Тесты и ограничения

`test_character_attack_locomotion_m210.py` проверяет реальные иерархии обоих
зарегистрированных архетипов и кодовые контракты смешивания, rollback и
периода. Тесты без Roblox engine **не могут доказать** корректность каждой
промежуточной позы, порядок PreSimulation и поведение при загрузке AnimationId;
нужен Studio Play. Миграций БД, перепубликации и Studio plugin install нет.
