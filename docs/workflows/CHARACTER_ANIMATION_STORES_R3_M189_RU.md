# M189 · R3: декомпозиция хранилищ Characters и Monster/NPC Animations

**База:** `game1_diag_2026-11-02_02-52-50.zip` (включает M186–M188). **Тип изменений:** только перенос обязанностей внутри Python, без новых операций/полей/API.

## Причина и границы

До этапа CharacterStore (834 строки) одновременно владел записью персонажа, канонизацией FBX, неизменяемой публикацией Roblox и генерацией JSON/Luau. MonsterAnimationStore (946 строк) сочетал SQLite-миграции, изменение слотов NPC/Monster, публикацию и регистрацию анимаций. Это создаёт зависимость проверок и смежных изменений от больших файлов.

### Characters

- `character_store.py` (250 строк) — стабильный публичный фасад, подключение к SQLite, строки архетипов, stats, active identity, статус. Сохранён `CharacterStore(root)` и все прежние методы.
- `character_core/archetype_contract.py` — единые константы схемы, расы/пол, default stats, версия публикационного pipeline. Старый модуль **реэкспортирует** их для совместимости.
- `character_core/model_workflow.py` — **целыми use cases** `register`, `assign_model`, `publish`, `publications`, `delete`; исходная обработка FBX и проверка костей, исходный порядок SQL и файловых операций без изменений.
- `character_core/registry_export.py` — `runtime_selection`, `snapshot`, `export`; генерация `character-archetypes.json` и `CharacterRegistry.luau`.

### Monster/NPC Animations

- `monster_animation_store.py` (469 строк) — прежний `MonsterAnimationStore(root, kind)`, классификация файла, scan/assign, чтение, manifest export и координация.
- `monster_animation_core/schema.py` — создание таблиц, SQL-миграции и нормализация legacy-источников.
- `monster_animation_core/bindings.py` — атомарные изменения weight/disarm/compatibility, rename и retire binding.
- `monster_animation_core/publication.py` — `publish_clip`, `publish_missing`, проверка подтверждённых ручных reimport Roblox.

Для Monster и NPC оставлен **один** контрактный store (существующий `kind`), сохранены публичные `classify`, `filename_rules`, статусные поля и разделение БД. Миграции не запущены на проектной БД только из-за патча: новый код содержит прежние операции и вызывается при прежнем старте.

## Инварианты

- Не меняются HTTP маршруты, сигнатуры публичных классов, SQLite schema, статусы, список registration IDs, Roblox Asset IDs, имена файлов, пути источников и версионирование.
- Все извлечённые методы сохранили тело и порядок действий; нет перехода на новую библиотеку/новый механизм загрузки.
- `system/verify/validators/` проверяет настоящих владельцев соответствующих контрактов вместо того, чтобы искать все методы только в монолитном файле; проверки `assets/prepared` распространяются и на новые writer-модули.
- Не изменяются `src/` (кроме существующих генерируемых файлов при обычных действиях), браузерный UI, runtime-скрипты, Studio Sync, документы самих анимаций.

## Контроль одинакового поведения

На двух изолированных временных окружениях, подставляя прежние файлы и рефакторинговые, с одинаковыми записями архетипа/опубликованного NPC-клипа и фиксированным временем **побайтно совпали SHA-256 всех четырёх генерируемых выходов**:

- `assets/manifests/character-archetypes.json`
- `src/shared/character/CharacterRegistry.luau`
- `assets/manifests/npc-animations.json`
- `src/shared/npc/NpcAnimationRegistry.luau`

Дополнительно: тесты M189 на делегирование фасада, no-op повторной публикации, опубликованные IDs, mutation NPC options. Имеющиеся тесты Character Assembly/NPC/scan/source-only выполняются без корректировки своих ожиданий. Статическая проверка Python/`verify.py` не заменяет Edit/Play Studio при будущих изменениях gameplay.

## Что остаётся на R3

- В `character_store.py` ещё есть смешение schema/active identity/stats. Их вынос целесообразен при следующей самостоятельной операции, без фиктивного дробления.
- В `monster_animation_store.py` пока вместе read/scan и registry export; будущая граница — сканирование/регистрация кандидатов и проекция в registry.
- `animation_core/storage.py` (~542 строки) отдельно обслуживает **Character Animations** и остаётся следующим кандидатом: он уже mixin, но совмещает SQL ownership, scan/assign и read projection; оценить вместе с `animation_core/registry.py` перед извлечением.
- Незавершённая staged-transaction/compensation для Character model replacement из M172 не решается «декомпозицией» и требует самостоятельного проекта изменений поведения.

**Применение:** один patch из корня `game1`, перезапуск только Control Center / Host Agent. Roblox Studio/Rojo/Blender ради такого рефакторинга перезапускать не требуется.
