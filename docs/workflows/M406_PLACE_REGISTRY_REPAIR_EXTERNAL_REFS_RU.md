# M406 · Place Registry Repair — exclude externally owned scan refs

## Проблема

Студийный `StudioPlaceRegistryInventory.Scan` сохраняет в одном `session.refs`:
- `p...`: подтверждённые размещения DecoManager с `row.placementId`;
- `x...`: подтверждённые подвесы LandscapePainter с `row.key`, но без `row.placementId`.

После M404 `StudioPlaceRegistryCommands` передавал **оба вида** в
`Repair.Apply` как `ctx.allRefs`. Сравнение `nil ~= ""` в Luau истинно,
поэтому попытка считать `allIds[nil]` останавливала Repair с ошибкой
`table index is nil`. HTTP API возвращал 400 до изменения Place.

## Контракт

- Полная таблица существующих `Placement ID` для Repair включает только
  размещения DecoManager (`p...`). Выбор пользователя остаётся строго
  ограничен ключами текущего Scan.
- `x...` никогда не получают Placement ID, не переименовываются и не
  становятся Deco-размещениями. Для подтверждённых подвесов сохраняется
  существующий механизм Sync Appearance/Physics.
- Если внутренний инвентарь managed-размещений не содержит строкового
  `placementId`, Repair останавливается с понятной диагностикой до записи.
- Дубликаты исправляются по алгоритму M404: одиночный Repair меняет выбранный
  ID; полный выбор группы оставляет один старый и перевыпускает остальные.
- Repair изменяет только метаданные размещения; pivot, CFrame, масштаб,
  MeshPart, кости, эффекты, крепления и коллизии не изменяются.

После установки: перезапустить Studio, выполнить `Scan Place → Repair All →
Scan Place → Sync` только на тех моделях, которым ещё требуется синхронизация.
Реальную Studio Edit-mode транзакцию необходимо подтвердить отдельно.
