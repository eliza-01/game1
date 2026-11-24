# M467 · Двухфазная анимация прыжка

Изменения только в клиентской презентации. M466 (единый `base_jump`) не применяется.

- `MovementController` владеет физическим прыжком и атрибутами `AnimationJumpSequence` (целое число, увеличивается после фактического `ApplyImpulse`) и `AnimationAirborne` (true от импульса до приземления, false при смерти). Физические параметры и ControllerManager не меняются.
- `CharacterAnimationController` читает эти атрибуты, но не записывает их. Проигрывает опубликованный `base.jump_start` однократно, по `AnimationTrack.Stopped` переключается на циклический `base.jump_loop` только если тот же персонаж ещё в прыжке. При приземлении возвращается к штатному Idle/Walk/Run. Повторный прыжок начинает `jump_start` заново. Все подписки очищаются при смене персонажа.
- Публикация ID остаётся в `CharacterAnimationRegistry`, разрешение — в существующем `AnimationResolver`; никаких скрытых ID, новых слотов или временных ригов. Если один клип ещё не опубликован, используется оставшийся либо прежняя наземная анимация без падения игрового процесса.
- `AnimationResolvedSlot` и `AnimationResolvedClip` доступны для диагностики через Studio Output/Attributes (`jump_start`, затем `jump_loop`).

## Studio Play / опубликованный Runtime — требуется ручная проверка

1. Убедиться, что в `CharacterAnimationRegistry.profiles.human_female.base` есть опубликованные `jump_start` и `jump_loop` с реальными `animationId`. При необходимости обновить Registry/Rojo после публикации.
2. Игрок Female без оружия: пробел/мобильный Jump. Сразу после принятого прыжка `AnimationAirborne = true`, `AnimationResolvedSlot = jump_start`; по окончании клипа — `jump_loop`; при посадке `AnimationAirborne = false`, возвращается Idle/Walk/Run.
3. Прыжок при движении/с оружием, быстрые повторные прыжки, смерть в полёте, смена персонажа. Никакого зависшего прыжкового трека после завершения.
4. Повторить на собранном Runtime и на медленной сети с прогревом M457.
