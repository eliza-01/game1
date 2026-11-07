# M251 · Location Assets — исправление Find при изменении Alpha

## Причина

M250 добавил режим `alpha` в ответ Studio-плагина (`StudioPublishedMeshHistory.Scan`),
когда Mesh ID и Texture ID актуальны, но `SurfaceAppearance.AlphaMode` нужно
синхронизировать. Валидатор Host Agent в `studio_deco_bridge.py` по-прежнему
разрешал только `texture`, `mesh`, `texture_mesh` и `current`, поэтому завершал
`Find Mesh IDs · Studio` ошибкой `invalid Studio ID scan result`.

Кроме того, поле `alphaPending` присутствовало в ответе Studio, но не передавалось
Host Agent в результат сканирования.

## Исправление

- Transport принимает `alpha` наряду с прежними режимами; версия протокола остаётся 9.
- `alphaPending` возвращается в отчёте, сверяется с числом управляемых MeshPart,
  у которых `needsAlpha=true`, и не скрывается от интерфейса.
- Булевы флаги `needsAlpha`, `alphaCurrent`, `alphaEnabled` валидируются, если
  Studio их прислала. Старые отчёты без этих полей поддерживаются.
- Для режима `alpha` запрещены противоречивые числа изменений геометрии
  или текстур; COL не может требовать Alpha Sync.

## Границы

Исправлена только серверная проверка ответа Studio Bridge. Не менялись
SQLite, Alpha-настройка ассета, публикация Model/Atlas, сами MeshPart,
Real Estate и Studio-плагин. Переустановка Studio-плагина не требуется.

## Проверка

1. В `Location Assets → Edit → Texture · atlas` включить Alpha и сохранить.
2. Нажать `Find Mesh IDs · Studio`. Отчёт должен показать `Alpha обновить: N`.
3. Одиночный Sync сначала проверить на копии Place. У визуального меша после
   Sync должен быть `SurfaceAppearance.AlphaMode=Transparency`.
4. Выключить Alpha, повторить Find и проверить Sync до `Opaque`.

Автотесты выполняют настоящий HTTP-обмен Host Agent / Studio Bridge для режимов
`alpha` и `current`, а также проверяют отказ при повреждённых Alpha-полях.

## Исправление транспортного whitelist (2026-11-07)

Повторная диагностика на реальном Place выявила второй дефект M251:
`DecoManager` и `StudioPublishedMeshHistory` вычисляли `alphaPending` правильно,
но `StudioDecoSyncCommands` не включал поле в whitelist результата `scan`.
Из-за этого Host Agent получал верхнеуровневое значение `0`, одновременно видел
`needsAlpha=true` у MeshPart и отклонял Find с `Studio alpha count mismatch`.

Whitelist Studio-команды теперь явно передаёт `alphaPending`. Контрактный тест
фиксирует наличие поля именно на границе Studio → HTTP, а диагностическая ошибка
Host Agent сообщает переданное и пересчитанное значения. Требуется переустановка
Studio-плагина; миграций данных и изменений размещённых моделей нет.
