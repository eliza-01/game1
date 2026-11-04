# M217 — полный аудит замен всех ассетов в MySQL 8.4

**Статус: CURRENT / SAFETY CRITICAL.** Журнал охватывает сохранённые публикации
Characters, Character Components, Character/Monster/NPC Animations, Weapons,
Monsters, NPCs, Texture Atlases, Location Assets и Real Estate. Подробные
per-instance события Studio Sync дополняют публикационную историю Location
Assets. Сам аудит не меняет FBX, текстуры, модели, анимации или Place.

## Источник истины и восстановимая история

Полная объединённая история хранится в MySQL 8.4, сервис Docker Compose
`asset-audit-db`, база `game1_asset_audit`. Named volume
`game1-asset-audit-data` переживает rebuild/restart контейнера. Порт `43823`
доступен только через `127.0.0.1`.

`SqliteAssetAuditImporter` читает существующие store-owned publication tables
только для чтения и идемпотентно проецирует каждую строку в MySQL. Источник
идентифицируется как `sqlite:<database>:<table>` + первичный ключ. Повторный
импорт не создаёт дублей. Для каждой логической пары asset/domain/slot
вычисляется предыдущий Roblox Asset ID. Повторная публикация новых bytes в тот
же ID сохраняется отдельным событием с новым SHA-256 и `oldId == newId`.

История, удалённая из SQLite до введения M217, автоматически невосстановима.
Начиная с M217, DELETE сначала обязан импортировать публикационные строки; при
недоступной MySQL удаление отклоняется. Синхронные публикации импортируются до и
после операции. Асинхронные Real Estate и Character Component jobs вызывают
импорт после успешной публикации.

Для Location Asset Studio Sync JSONL
`.control-center/location-asset-studio-sync-history.jsonl` остаётся write-ahead
log. Атрибут `Game1DecoSyncHistory` хранит только последние 32 операции и не
является полной историей.

## Схема

Версионированная миграция:
`system/control-center/migrations/asset_audit_mysql/001_location_asset_sync_audit.sql`.

- `asset_replacement_operations` — публикация, assignment или Studio Sync;
- `asset_replacement_changes` — пары old/new Roblox Asset ID;
- `asset_replacement_instances` — конкретный `instanceId` и Studio path;
- `asset_replacement_instance_changes` — изменения внутри экземпляра;
- `asset_audit_schema_migrations` — имя и SHA-256 миграции.

Событие содержит domain, key, slot, тип ресурса, source SHA-256, Open Cloud
operation path, время UTC и источник записи. FBX, изображения, анимационные
файлы и Place в MySQL не сохраняются. UPDATE/DELETE audit rows приложением не
реализованы.

Чтение: `GET /api/asset-replacements` с фильтрами `domain`, `key`, `limit`,
`before`. Control Center раздел `asset history` показывает страницы журнала.

## Отказы, backup и rollback

Недоступная MySQL не мешает запуску Host Agent и обычным read-only операциям,
но блокирует публикацию/замену/удаление, для которых аудит обязателен. Уже
успевшая завершиться удалённая публикация остаётся в SQLite и будет импортирована
при восстановлении.

1. Установить `system/control-center/requirements-host.txt`.
2. Запустить `docker compose up -d asset-audit-db` из `system/control-center`.
3. Одинаково задать `GAME1_ASSET_AUDIT_PASSWORD` Compose и Host Agent при
   переопределении локального пароля.
4. До первого импорта сохранить SQLite и JSONL; импорт не изменяет источники.
5. Для SQL backup использовать `mysqldump --single-transaction`.
6. Никогда не выполнять `docker compose down -v`: `-v` удалит volume истории.

Rollback кода: остановить новые публикации/Sync, вернуть предыдущий Host Agent и
оставить volume нетронутым. Миграция аддитивна и проверяется по SHA-256.

## Проверка

- importer: повторный запуск не создаёт дублей, old/new ID сохраняются;
- retention: больше 50 операций доступны постранично;
- deletion: при недоступной БД отклоняется до удаления source history;
- async jobs: импорт вызывается после успешной публикации;
- Studio bridge: число per-instance записей равно числу изменённых моделей;
- статические тесты не заменяют Studio smoke на копии Place.
