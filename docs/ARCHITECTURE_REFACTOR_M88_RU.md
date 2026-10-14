# M88 — декомпозиция Host Agent: POST/DELETE

**База:** дамп `game1_diag_2026-10-14_10-58-18.zip` (после M87).

## Границы модулей

| Модуль | Ответственность |
| --- | --- |
| `host_agent.py` | Сборка зависимостей, привязка `127.0.0.1`, HTTP-token, чтение JSON и отправка ответа. Также содержит существующие Studio sync / native picker функции — следующий этап декомпозиции. |
| `api/write_dispatch.py` | Транспортно-независимое распределение POST/DELETE; неизвестный маршрут — `(404, {"error": "not found"})`. |
| `api/write_files.py` | Выбор исходных файлов, папки анимаций, приём экспортированных RBXM. |
| `api/write_actors.py` | Регистрация и публикация Character / NPC / Monster / Weapon, синхронизация с Studio, экипировка. |
| `api/write_world.py` | Location Assets, Locations, Spawn Points, Timeline editor и Options. |
| `api/write_animations.py` | Анимационные реестры и публикации, совместимость, веса и скорость анимации. |
| `api/delete_entities.py` | Удаление регистраций и binding с прежними проверками использования. |

**Контракт:** `route(path: str, body: Callable, deps: Mapping) -> tuple[int, JSON] | None`. `body()` вызывается только обработчиком выбранного маршрута; `None` означает, что маршрут данному домену не принадлежит. Зависимости передаёт единая точка сборки `WRITE_SOURCES`; доменные модули не импортируют Host Agent, не открывают самостоятельно БД и не отправляют HTTP-ответы. HTTP-авторизация выполняется до диспетчеризации.

## Совместимость

- POST/DELETE URI, ответы `200/400/401/404`, legacy-параметры, порядок вызова хранилищ и вызовов Studio сохранены.
- Устранены ранее необъявленные суффиксы `publish-missing` для Character и Monster Animation (вместо `NameError` выполняется существующий метод публикации).
- Сохраняется важное поведение M78/M84: удаление animation binding делегируется в store (архивирование Asset ID), сканирование создаёт новую локальную регистрацию; M88 не переносит и не воссоздаёт старые ID.
- Миграции SQLite/реестров, перерегистрация или перепубликация ассетов **не требуются**.
- В текущей реализации последовательное удаление связанных регистраций NPC/Monster не является единой межхранилищной транзакцией. M88 сохраняет прежнюю последовательность и тестирует запрет удаления при активном использовании; ввод атомарной операции — отдельный будущий этап.

## Регрессия

- `python system/verify/verify.py`
- `python -W error::ResourceWarning -m unittest discover -s system/verify -p 'test_*.py' -q`
- `test_http_write_contracts_m88.py`: регистрация/изменение, все старые POST-маршруты, нулевые веса, публикации `publish-missing`, guards удаления, запрет побочных эффектов для неизвестного пути, контракт dependency injection.
- `test_http_read_contracts_m85.py`: HTTP-интеграция с `ThreadingHTTPServer`, токеном и подставными хранилищами для POST/DELETE/GET.
- `test_animation_remove_rescan_m78.py`: реальные временные SQLite и повторное сканирование после удаления.

**В этой среде не проверено:** работа Host Agent против запущенного Windows Control Center, реальная публикация в Roblox Open Cloud и реальный интерфейс Studio. После применения проверить регистрацию NPC, Scan Folder, Remove, Publish и состояние Host Agent. Ни один игровой Luau-скрипт не изменён.

## Дальнейшая декомпозиция

1. Вынести нативные диалоги, выгрузку анимаций и `sync_*_to_studio` из composition root в отдельные сервисы, сохраняя подписи функций и контракты Bridge.
2. Прописать транзакционные границы и восстановление для удаления связанных записей из нескольких stores.
3. Декомпозировать `MonsterSpawnerService` на spawn/factory, runtime population, animation, death/respawn (с проверками внутри Roblox Studio).
