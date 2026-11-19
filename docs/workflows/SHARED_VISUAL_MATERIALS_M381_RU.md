# M381 · Общая палитра материалов MeshPart

Единый каталог Roblox `Enum.Material` расположен в
`system/control-center/services/mesh_visual_appearance.py`.
Он основан на Creator Hub (https://create.roblox.com/docs/reference/engine/enums/Material).
Из 45 значений 2 предназначены только для Terrain (`Air`, `Water`);
`ForceField` требует особой UV-текстуры, поэтому отображается как недоступный
для режима Material + Color. Остальные 42 материала доступны.

`LocationAssetStore.options()` и `/api/real-estate` возвращают одни и те же
элементы `visualMaterials`. В обоих редакторах нет собственных списков.
Оба хранилища используют `mesh_visual_appearance.validated()` при записи.

Studio: `StudioTextureAppearance.ApplyVisual()` применяет Material + Color
или Atlas ко всем визуальным MeshPart. Проверка и преобразование
Enum.Material/Color3 также выполняется здесь (`MaterialColor()`),
а не в адаптере Location Assets. Только явный `alphaEnabled=true` с атласом
разрешает SurfaceAppearance. Семантический sound material не затронут.

Контракт не мигрирует сохранённые материалы, атласы или Plot-привязки.
