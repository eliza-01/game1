# M89 — Host Agent: независимые Studio / файл-сервисы

**База:** M88 (дамп `game1_diag_2026-10-14_10-58-18.zip` + M88), схема БД и Roblox runtime без изменений.

## Изменения и границы

- `host_agent.py` — composition root: создание хранилищ, передача зависимостей, авторизация и HTTP-адаптер. Уменьшен с ~562 до 231 строки.
- `services/studio_asset_sync.py` — только синхронизация опубликованных Character, Weapon, Monster и NPC моделей с Studio. Конструктор получает репозитории и функцию Bridge; модуль не импортирует Host Agent / API / SQLite.
- `services/studio_rig_validation.py` — единый контракт проверки опубликованных костей, артикуляции, списка отсутствующих Bone. Сохранены существующие тексты ошибок Character и Monster. Может повторно использоваться другими Studio-инструментами.
- `services/native_pickers.py` — PowerShell Windows Forms для выбора FBX, текстур и каталога анимаций. Контракт отмены (`""` или `[]`), разделитель множественного выбора и `GAME1_ANIMATION_PICKER_INITIAL_PATH` сохранены.
- `services/animation_export.py` — запись экспортированного RBXM с прежней нормализацией имени, валидацией base64/лимита 64 MiB и атомарной заменой временного файла.
- `host_agent.py` передаёт методы сервиса в прежний `WRITE_SOURCES`; доменные обработчики M88 не изменены.

### Контракты

- Все прежние HTTP URL, статус-коды, аргументы и структуры ответов оставлены без изменений.
- Предсинхронизация при `npc-spawns/place/register` сохранена. Проверка `readiness` перед `place` сохранена.
- Синхронизация Monster и NPC использует соответствующий репозиторий и тот же `monster-rig` Bridge, включая `expectedBones` и проверку опубликованных текстур.
- Не меняются `Animation ID`, публикация, SQLite, реестры, Luau-скрипты или Rojo.
- Для M89 **нет миграций**.

## Регрессия

- `python system/verify/verify.py`
- `python -W error::ResourceWarning -m unittest discover -s system/verify -p 'test_*.py' -q`
- `test_host_agent_services_m89.py`: фейковый Studio Bridge и репозитории проверяют выходные модели, пути, метаданные, Bone validation, отказы, текстуры; нативные диалоги мокируются; файловый экспорт тестируется в временном каталоге.
- Существующие M85/M88 HTTP-контрактные тесты проверяют передачу зависимостей, авторизацию, GET/POST/DELETE, Scan/Remove/Publish маршруты.

**Не выполнялось в контейнере:** реальный Windows диалог, подключение активной Roblox Studio и публикация через Roblox Open Cloud. После применения достаточно проверить выбор папки в Asset Manager, Studio Bridge Sync NPC/Monster/Weapon и Animation Export; игровое поведение не менялось.

## Следующий этап

- Разделить `MonsterSpawnerService` на независимые `factory`, `population`, `animation` и `death/respawn` без переписывания игровой логики. Для этого нужен актуальный дамп после применения M89 и тест запуска Play.
- Транзакционное межхранилищное удаление — отдельный этап с миграциями/восстановлением при необходимости, не совмещать с разбором Roblox runtime.
