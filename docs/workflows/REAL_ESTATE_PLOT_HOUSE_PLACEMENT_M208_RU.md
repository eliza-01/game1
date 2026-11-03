# M208 · Real Estate Placement — авторские точки для участков

## Назначение

Пять размеров/профилей домов на 50 участках: **каждая пара `(plotIndex, houseSlug)` имеет собственную точку**. Это authoring-система; покупка, владение, экономические проверки и runtime-spawn не добавляются этим патчем.

## Рабочий процесс

1. В Roblox Studio **Edit mode** открой карту с `Workspace.Plots/01` … `Workspace.Plots/50`, с `plot_01_volume` … `plot_50_volume` (для однозначных номеров также поддерживается `plot_1_volume`).
2. Помести модель дома в `Workspace`, отрегулируй позицию, поворот и **uniform Model scale**. Выдели **ровно один Model** с именем, в точности совпадающим с зарегистрированным slug (например, `house_level3_01`). Не выделяй отдельный MeshPart, volume участка или содержимое ServerStorage.
3. В Control Center → Real Estate → **04 · Placement** выбери зарегистрированный дом и `Plot 01`–`Plot 50`, нажми **Bind selected Model**.
4. Studio Bridge проверяет модель и наличие соответствующего volume участка. Считывает `Model:GetPivot()`, `Model:GetScale()` и `volume.CFrame`. Никаких изменений в Workspace операция Bind не производит.
5. Host Agent сверяет идентификаторы/операцию и математическую согласованность трансформаций, сохраняет запись и revision. Повторный Bind обновляет только эту пару. Список и status обновляются без перезагрузки страницы.

## Хранение

- SQLite: `.control-center/game1_real_estate.db`, таблица `real_estate_placements`, ключ `(plot_index, house_slug)`.
- Версионированный экспорт: `assets/manifests/real-estate-placements.json`, `schemaVersion: 1`, в стабильном порядке по plot/slug.
- Поля: `worldCFrame` (12 компонентов), `plotCFrame` (12), `localCFrame` (12), `scale` (число), `plotVolume`, `revision`, `updatedAt`.
- `localCFrame = plotVolume.CFrame:ToObjectSpace(selectedModel:GetPivot())` — будущая **основная** точка для размещения приобретённого дома относительно участка. Мировой transform — авторский снимок и диагностика. Для будущего runtime: `model:ScaleTo(scale)` и `model:PivotTo(currentVolume.CFrame * localCFrame)` после сборки опубликованного дома и проверки покупки (runtime-реализация не входит в M208).
- Удаление регистрации дома убирает только связанные с ней точки, не меняя остальные дома, модели и атласы. Отдельное место под map scope пока не требуется: текущая карта содержит единственный каталог Plots 01–50.

## Ответственность

| Модуль | Ответственность |
|---|---|
| `real_estate/placement.py` | Валидация, SQLite-репозиторий, атомарный JSON экспорт |
| `services/studio_house_placement_bridge.py` | Одноразовый HTTP-командный обмен через существующий Studio Bridge :43137 с operationId |
| `api/real_estate.py` | Тонкие HTTP GET/POST адаптеры |
| `StudioHousePlacementCapture.luau` | Выбор в Studio, проверка Workspace/Plots, чтение CFrame/scale |
| `real-estate-placement.js` | UI управления и просмотра сохранённых точек |

Серверное применение дома игроком **не входит** в этот этап. Привязка **не** публикует ассеты, не изменяет gameplay, не меняет Plots и не загружает модели.

## API v1

- `GET /api/real-estate/placements` → `{schemaVersion, plotCount, items}`.
- `POST /api/real-estate/placements/bind` с `{houseSlug, plotIndex}`. Значения CFrame нельзя отправлять из браузера: они принимаются только как результат текущего Studio Bridge-запроса `house-placement-capture`.
- Ошибка при отсутствующем volume, несовпадении имени выделенной модели, Play mode, отсутствии Studio Bridge, занятом порте или устаревшем ответе; существующая запись в таких случаях не изменяется.

## Проверки и риски

Изолированные тесты `test_real_estate_house_placement_m208.py` проверяют разные дома на одном plot, повторную привязку, проверку CFrame, отсутствующие имена/публикации, каскадную очистку только собственных точек, реальный локальный HTTP round-trip. Синтаксис JavaScript и Luau валидируется отдельно.

В Roblox Studio нужно вручную проверить: считывание `Model:GetScale()` после использования модельного Scale tool; порядок 12 компонентов CFrame, доступность плагина Edit mode; расположение меток при будущем player-spawn. Не полагаться на изменение отдельных `BasePart.Size` как на равномерный Scale всей Model: для такой геометрии `Model:GetScale()` не является полным описанием изменений формы.
