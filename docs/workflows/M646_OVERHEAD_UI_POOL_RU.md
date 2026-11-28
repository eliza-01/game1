# M646 · Overhead UI Pool

База: game1_diag_2026-11-28_16-21-34.zip, M645. KBN-0037 T05/A05. CODE_COMPLETE; Studio/DEV/Mobile NOT_RUN.

## Контракт

- `MnpcOverheadRegistry`: регистрация Model и готовности RootCollider / ImportedRig / MeshPart, LifeState, local LOD и server demand. События release/death/streaming немедленно снимают lease; старые deferred callback защищены идентичностью записи. При отсутствии `Game1MnpcKind` допускается прежний unmanaged контракт с RootCollider. Registry не создаёт UI.
- `OverheadVisibilityPolicy`: отдельные Monster/NPC правила; player-centered дистанция, reticle/lock/aggro, preview, независимые NPC name/HP, GP owner/zone/group/icon-only. Raycast ищет зарегистрированную FULL-ready модель без зависимости от существования GUI.
- `MnpcOverheadController`: один Heartbeat 0,1 с; обход только FULL-ready записей, без нового spatial index и изменения CanQuery. Дистанция через CharacterSpatialRoot. Не сортирует всю популяцию: только ожидающие видимого view заявки. Новые allocation до 4 за тик, reuse сразу, приоритет HP и aging после 1 с, без hard cap. При массовом входе возможна задержка появления отдельных UI на несколько тиков. Отдельные OverheadHealthController/NpcOverheadController удалены.
- `OverheadViewPool`: один общий ленивый кэш, 8 свободных views, TTL 5 с, без стартового прогрева. Acquire/Release/Clear; ошибки Bind/Unbind явно диагностируются. Повтор Bind после ошибки ограничен 2 с. `HealthBarView` раздельно создаёт дерево и привязывает модель; HP событийное, отмена Tween, initial fill без старой анимации, generation guard, уничтожение GP портрета, очистка model/anchor/Adornee/parent/locale и динамического текста. NPC camera cap сохраняется при refresh стиля. `LanguageState` пропускает только явно локализуемые самим view labels, иначе reparent накапливал бы listeners.
- `SelfOverhead`: отдельный экземпляр общего API, прежняя self policy; экранный HUD не менялся. PlayerGui/character reset очищает пул и self. Stop очищает registry, connections, pool; Start идемпотентен.
- Не меняются серверные скрипты, LOD thresholds/demand, AI, боевая логика, данные Options, сетевые события, схема ассетов. Native GUI appearance/input, Studio и опубликованная игра требуют приёмки.

## Проверки

- `test_m646_overhead_ui_pool.py`: 3/3 PASS. Реальные policy, pool, registry в Lua doubles, 2376 сравнений с независимым M645 oracle. HealthBarView source syntax-adapted для texlua: rebind Monster→NPC→Monster, актуальное HP, отмена Tween, старый callback, GP portrait, locale и NPC distance cap. Не нативный Roblox и не полноценный Luau parser.
- 85 профильных проверок M320/M321/M322/M329/M331/M332/M337/M362/M543/M556/M583/M600/M638/M639/M640/M644: 80 PASS, 3 FAIL и 2 ERROR также на чистом M645. M337 устаревшие HTML count и AI guard; M321 устаревшая строка damage resolver; M543/M600 отсутствуют raster/SVG в дампе. Старые тесты не удалены и не заявлены как PASS. Guards мигрированы на реальных новых владельцев.
- `validate_luau.py` (узкий Studio plugin preflight) и `verify.py` PASS. Нативные Luau compile, Studio Play, published DEV, PC/Mobile, массовая нагрузка и замеры CPU/RAM/FPS NOT_RUN. Точный выигрыш не заявляется.

## M647 / короткая проверка

M647 реализован: см. [M647_OVERHEAD_INTEGRATION_RU.md](M647_OVERHEAD_INTEGRATION_RU.md). Ниже остаётся сценарий нативной приёмки.

Обычная игра: подойти к NPC, отойти и вернуться; навестись на монстра, атаковать, потерять фокус; перейти FULL→LOD1→UNLOADED→FULL; смерть/респавн; EN/RU, desktop/mobile preview и GP при наличии. Убедиться, что GUI не появляется на dummy, старые имена/HP не переходят между существами, действие оружия/камеры не изменилось. Отдельная проверка GUI reset, streaming и нативной ресурсной стабильности остаётся открытой. Не требовать стресс-тестов от владельца.

Далее: Character Creation Prewarm, Hitbox Precompute, Priority Animation Prewarm, Player Attack Sampler. Socket & Door отложен. Не добавлять отдельный M648 без конкретного дефекта.
