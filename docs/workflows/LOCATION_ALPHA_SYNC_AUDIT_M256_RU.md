# M256 · Location Alpha Sync: атомарная граница Studio → аудит

## Причина

Alpha-only Sync успешно менял `SurfaceAppearance.AlphaMode` в Studio, но затем
Host Agent отклонял результат. `LocationAssetSyncHistory` принимал только
числовые Model/Atlas ID, тогда как Studio отправляла событие `kind=alpha` со
значениями `Overlay`, `Transparency` или `Opaque`. Из-за ошибки после изменения
Place браузер показывал Sync как неуспешный и оставлял старый отчёт Find.

Дополнительно `tostring(Enum.AlphaMode.Overlay)` давал нестабильное для этого
контракта значение `Enum.AlphaMode.Overlay`, превышающее поле аудита MySQL.

## Контракт

- Studio передаёт для Alpha только имя enum: `Overlay`, `Transparency`,
  `TintMask`, `Opaque`; отсутствие `SurfaceAppearance` записывается как `missing`.
- Host Agent совместимо нормализует старую форму установленного плагина
  `Enum.AlphaMode.<Name>`; после нормализации в WAL/MySQL хранится только `<Name>`.
- `missing` допустим только как предыдущее значение.
- Остальные виды изменений по-прежнему принимают только числовые Asset ID.
- WAL записывается до MySQL, а успешный аудит позволяет API подтвердить Sync и
  выполнить повторный Find.

Изменения не затрагивают Model/Atlas публикации, геометрию, CFrame, Size,
физику или Real Estate.
