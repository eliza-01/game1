# M230 — Real Estate Placement: совместимость старых биндов

## Причина

M229 добавил обязательное поле `houseAnchorLocalCFrame` для **новых** Bind,
но старые M208–M228 записи уже хранили `worldCFrame`, `plotCFrame`,
`localCFrame`, `scale` и `anchored`. Они были ошибочно заблокированы в UI,
Studio Bridge и Studio-плагине. На дампе 2026-11-05 04:01:50:

| House | Всего биндов | С house anchor | Без house anchor |
| --- | ---: | ---: | ---: |
| `house_level1_01` | 39 | 39 | 0 |
| `house_level3_01` | 39 | 0 | 39 |

## Контракт M230

**Один и тот же** механизм `StudioRealEstateHouseFrame.Align` обслуживает
оба формата. Старые данные не интерпретируются как новые и не мигрируют
искусственными нулевыми offsets.

1. Если `houseAnchorLocalCFrame` — CFrame из 12 чисел, используем авторский
   pivot MeshPart `house`, как в M229 (`house-anchor-v2`).
2. Если поле равно `null`/отсутствует, берём текущий offset опубликованного
   `house` в подготовленном клоне относительно pivot **этого же клона**.
   Это даёт старое поведение `Model:PivotTo(plot.CFrame * saved.localCFrame)`
   (режим `legacy-model-pivot`), но вызывает централизованный `HouseFrame.Align`.
3. Если поле присутствует, но имеет неверную форму — операция отклоняется.
4. `Place` и `Place all` разрешены для legacy и нового формата, в том числе
   для смешанных комплектов. UI помечает legacy строки, Studio возвращает
   `rotationMode`/`legacyPlacements`, корневой preview имеет
   `Game1PlacementRotationMode`.
5. Никаких миграций SQLite, исправления CFrame, изменения исходных Binding,
   изменения `revision`, новых алгоритмов клонирования или синхронизации нет.
6. `Clear`, `Clear all`, Anchor/Free, сохранённый `scale`, `anchored`, Undo,
   stage-before-destroy и защита чужих объектов не меняются.

### Важное ограничение

Offset между оригинальной выбранной Model и её `house` MeshPart **не был
сохранён** старым Bind. Legacy Place теперь повторяет историческое поведение,
но **не гарантирует визуальное совпадение с исходной авторской ориентацией**
после изменений FBX/pivot. Если нужна точная ориентация, можно повторно Bind
нужной пары; это необязательно для доступности Place. Нельзя автоматически
приписать таким данным «точно восстановленный house pivot».

## Версионирование

Preview-команда Host Agent / Studio: `house-placement-preview-v4`,
`schemaVersion=4`. Старый Studio-плагин v3 не примет v4 и не должен тихо
использовать старую реализацию. Capture остаётся
`house-placement-capture-v2` / schema 2.

## Установка / проверка

- Установить Git-патч поверх M229, затем запустить
  `system/studio-plugin/install.ps1`, перезапустить Host Agent и полностью
  переоткрыть Studio, обновить браузер Ctrl+F5.
- На **копии Place** выбрать `house_level3_01` и один старый Plot.
  Убедиться, что Place доступен, сообщает `legacy Model-pivot alignment` и
  располагает дом по сохранённому Model CFrame; проверить визуальный поворот.
- Затем отдельно проверить `Place all`: 39 старых биндов и одна Undo-операция,
  никакие чужие объекты не затронуты. `house_level1_01` продолжает использовать
  `house-anchor-v2`.
- Реальное поведение Roblox Studio **не проверено** в среде сборки патча.

## Тесты

Серверная обработка 39 legacy биндов из SQLite, поддержка смешанного
пакета, строгая проверка повреждённого anchor, версия Bridge и UI-фильтрация,
`verify.py`. Конкретный список прогонов указан в отчёте M230.
