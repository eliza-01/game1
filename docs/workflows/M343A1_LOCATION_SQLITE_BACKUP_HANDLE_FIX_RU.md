# M343A1 — закрытие SQLite backup handles в LocationAssetStore

**База:** установленный M343A. **Затронуто:** только Python Control Center и тесты. **Нет миграции данных**.

## Симптом

На Windows (Python 3.13) тесты `test_location_collision_blueprint_m343.py` завершались `WinError 32`, так как `TemporaryDirectory` пытался удалить временные файлы `location_alpha_m250_*.sqlite` из `.control-center/backups/`. В предыдущих стадиях программы открывались SQLite backup destinations через стандартный `with sqlite3.connect(...)`, который коммитит/откатывает транзакцию, **но не закрывает connection**.

## Исправление

Четыре схемных backup-подключения в `LocationAssetStore._init` (M232, M249, M250, M256) теперь используют уже существующий `sqlite_connection.connect()` (`ClosingConnection`). Его контекстный менеджер завершает транзакцию **и закрывает файловый дескриптор**. Формат и состав backup не меняется.

Добавлен тест, который при первом открытии чистого реестра записывает возвращённые backup connections, проверяет наличие каждой из четырёх резервных копий и проверяет, что дескрипторы закрыты. Тест независим от ОС: обращение к закрытой SQLite connection обязано выбросить `sqlite3.ProgrammingError`.

## Проверка

```powershell
python -m unittest discover -s system\verify -p "test_location_collision_blueprint_m343.py" -v
python system\verify\verify.py
```

Изменения касаются только Python Control Center; плагин Roblox Studio, Rojo, Place, опубликованные Asset ID, коллизии и игровые данные остаются без изменений. **Миграцию M342 повторять нельзя и не требуется.** Если Control Center запущен, перезапустить его для использования исправленного Python кода.
