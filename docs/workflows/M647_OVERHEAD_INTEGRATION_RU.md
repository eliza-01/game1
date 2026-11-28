# M647 · Overhead UI integration

База: M645 + M646. KBN-0037 T05/A05. CODE_COMPLETE. Дополнение M648: владелец подтвердил функциональную приёмку («все нормально»); T05 выполнена, полная A05 и замеры NOT_RUN.

## Исправления

- Поздняя репликация нескольких MeshPart внутри готового ImportedRig отмечает dirty offset. Существующий общий тик обновляет высоту только привязанного view, один раз для группы событий. При новом Bind bounds уже вычисляются. Новых циклов нет.
- Folder callbacks проверяют поколение регистрации и фактическую принадлежность модели. Отложенные события старой регистрации не удаляют новый lease после Stop/Start или замены папки. События LOD/death/remove сохраняют немедленное освобождение.
- M321: проверяется положительный applied damage и итоговый Miss только на последнем HitEnd, по актуальному AttackSessionStore. M337: проверяются прежние секции Options по уникальным ключам и актуальная HomeLeash/DeathChase цепочка. Серверные механики не изменялись.
- M543/M600: исходные графические payload проверки пропускаются только для точных путей из `_dump/model_files.json`; неизвестная пропажа — FAIL. Проверки runtime UI и raster data выделены отдельно и выполняются без оригиналов. Полный проект с файлами проходит прежние проверки содержимого без пропуска.

## Автоматические проверки

98 профильных тестов (M320/M321/M322/M329/M331/M332/M337/M362/M543/M556/M583/M600/M638/M639/M640/M644/M646/M647/M439): 96 PASS, 2 SKIP (исключённые payload), 0 FAIL/ERROR. Реальные registry/pool/policy, 2376 oracle cases, реальный HealthBarView и координатор в Lua doubles (с адаптацией Luau syntax): first focus без заранее созданного GUI, LOD release/rebind, 4 новых view за тик, NPC name/HP, late meshes с coalescing, PlayerGui reset, Stop/Start, stale callback. `validate_luau.py` (узкий plugin preflight), `verify.py`, Git apply/reverse-check и diff-check. Это не нативный Roblox и не полный Luau compile. Полный глобальный набор не запускался.

## Приёмка и следующее

Studio Play, опубликованный DEV, физический телефон, A05 и фактические CPU/RAM/FPS NOT_RUN. После ответа владельца T05 функционально закрыта; A05 не закрывать до ресурсного evidence. Короткая обычная игра: подход/уход от NPC, наведение/бой с монстром, переход FULL/LOD1/UNLOADED, респавн, язык и GP при наличии. Без обязательных стресс-тестов или новых диагностических панелей. Если выявится реальная регрессия — исправить её, иначе следующий этап Character Creation Prewarm, далее Hitbox Precompute, Priority Animation Prewarm, Player Attack Sampler. Socket & Door, общий Profiler и Incremental Studio Preview отложены.
