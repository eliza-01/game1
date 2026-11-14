# M342S — закрытие SQLite-соединений в миграторе COL Mesh

## Причина

`sqlite3.Connection` при использовании `with sqlite3.connect(...) as conn` завершает транзакцию,
но **не вызывает** `conn.close()`. На Windows / Python 3.13 из-за этого в тесте
`test_migration_dry_run_does_not_change_database` оставался открытый дескриптор
`game1.db` во временной папке. Удаление каталога завершалось `WinError 32`.
В M342R были закрыты соединения, создающие тестовые базы, однако внутри
`m342_retire_col_mesh.py` соединения по-прежнему оставались открытыми.

## Исправление

- `sqlite_connection(...)` гарантирует commit/rollback и вызов `close()` через `finally` контекстных менеджеров.
- Исправлены пути dry-run, записи миграции и создания резервных копий SQLite.
- Тест M342 теперь проверяет вызов `close()` для обоих соединений независимо от ОС.
- Никаких изменений реестров, опубликованных Asset ID, Roblox Studio или COL cleanup нет.

## Применение

Патч M342S применяется **поверх M342R**. Миграцию M342 заново запускать не нужно:
по логу пользователя она уже выполнилась успешно. После тестов необходимо
выполнить установку плагина Studio, которую предыдущий PowerShell-блок не достиг
из-за ошибки теста, затем перезапустить Roblox Studio в Edit Mode.

## Проверка

`python -m unittest discover -s system/verify -p "test_col_mesh_retirement_m342.py" -v`

`python -m unittest discover -s system/verify -p "test_m342r_col_cleanup_regression.py" -v`

`python system/verify/verify.py`

Сведения о фактическом удалении COL в Workspace подтверждаются только в Roblox Studio.
