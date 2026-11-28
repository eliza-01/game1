# M629 · MNPC AI / Pose Binding — продолжение M628, шаг 2

База: свежий dump `game1_diag_2026-11-28_05-08-35.zip` + M628. Действующее ТЗ: [MNPC](MNPC_LOD_SPEC_RU.md); KBN-0037-T08/A07 остаются открытыми.

## Реализовано

- Общий `actor/MnpcPoseBinding`: AI регистрируется без обязательного Animator/готового presentation. Begin/Commit/Abort/Release/Close — один контракт для Monster и NPC; ticket имеет уникальную identity, повторное/чужое/отменённое завершение не принимается. Закрытие инвалидирует ожидающую подготовку. Доменные владельцы освобождают отклонённые native payload; никакого таймера или remote в binding нет.
- Monster: `MonsterAgentLifecycle` регистрирует навигационный root/Humanoid, AI state и scheduler до native track binding. `Game1MnpcRigReady` теперь только инициирует подготовку боевых tracks через событие, а не разрешает создание AI. Проверки live actor, Animator ancestry и ticket перед commit; late result уничтожается. Native combat tracks принадлежат combat presentation, spawn idle/death tracks остаются у population. На death отменяется pending, обычный fade сохранён, финальный release освобождает run/combat-idle tracks. Home и MonsterSpawning выставляются до publish, чтобы ранний AI не нарушал существующий underground reveal.
- NPC: `NpcCombatAIService.Bind` больше не принимает presentation, регистрирует navigator, home, retaliation policy и scheduler отдельно. `NpcMotionIntent` хранит команды движения/возврата/боевого состояния и передаёт их в реальный presentation после AttachPresentation. Повторный attach или late result после Unbind отклоняется. Спавнер регистрирует entry и cleanup до загрузки native tracks, затем commit; на Dying существующая death presentation сохраняется у спавнера. Никакой фиктивной атаки или имитации animation callbacks.
- Normal Monster attack, special cast и NPC beginAttack требуют готового native binding до начала действия; существующие authored timelines, fallback length, Hit callbacks и serial cancellation сохранены. Контракт binding — наличие принятого payload, не доказательство завершения engine evaluation или гарантированного CDN load. Существующие OBB, геометрия RootCollider, AI policy, scheduler, navigation, respawn и Location/House LOD не переписаны.

## Границы этого шага

Оба AI теперь имеют отдельную регистрацию и native presentation binding, однако production всё ещё создаёт полный риг и hitbox на spawn; NPC по-прежнему получает weapon metadata от полного equip до Bind. Не включать shell-only production, pose dormancy или снятие Game1MnpcRigReady у живого actor: для этого ещё требуются независимые metadata/collider, action demand/readiness, безопасное отключение активных consumers, detach/reacquire и проверка отсутствия репликации carrier у дальнего клиента. Binding.Release — общий механизм инвалидирования, не разрешение отключить текущую боевую позу. NPC pin теперь выполняется на этапе регистрации до native tracks; положение, native welding/animation и spawn timing требуют Studio smoke. Engine two-client и A07 NOT_RUN. Никакого заявленного выигрыша FPS. Шаг M628 не закрыт.

## Проверка и продолжение

`test_m629_mnpc_ai_pose_binding.py` исполняет реальные binding и motion intent через Lua oracle: cross-incarnation ticket, pending cancellation, stale commit, replay/release/rebind, close; source contracts для обоих production AI entrypoints и action gate, хэши прежних attack/cast/presentation bodies. Старые source tests обновлены строго на новый API; M615 сравнение нормализует только имя получателя motion intent. Это не исполнение native Roblox AI/physics.

Далее: вынести метаданные размеров/RootCollider и equipment state из обязательного per-instance FULL clone; обеспечить shell-only spawn/movement для обоих доменов и lifecycle реального acquire/release без смены identity/HP/home; только затем включать server demand и per-client LOD по ТЗ. Проверка обычной игрой, без нового обязательного stress/profiler.
