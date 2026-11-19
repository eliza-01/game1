# M382 · Material + Atlas · единый визуальный контракт

Три режима для Real Estate (каждый MeshPart) и Location Assets (редактор ресурса):

- `material`: Material + Color, `TextureID` пустой, `SurfaceAppearance` удалён.
- `atlas`: TextureID из Atlas Registry; Material/Color сбрасываются к SmoothPlastic/white при Location Studio Sync; `SurfaceAppearance` — только при явном `alphaEnabled=true`.
- `material_atlas`: Material + Color и опубликованный TextureID одного MeshPart. Atlas Registry, ревизии, публикация и Studio Sync используются те же. Явный `alphaEnabled=true` создаёт `SurfaceAppearance` как в `atlas`.

**Ограничение Roblox:** TextureID может визуально перекрывать текстуру Roblox Material на одном MeshPart. Для одновременного видимого отображения разных поверхностей необходимо разбить геометрию на отдельные MeshPart с разными режимами. При `SurfaceAppearance` с прозрачностью Roblox Material также не становится вторым смешиваемым слоем. Режим `material_atlas` сохраняет свойства одновременно, но не эмулирует шейдерное наложение материалов.

Миграция SQLite не нужна: существующие текстовые поля `appearance_mode` / `mesh_options_json` поддерживают новый токен. Старые `material` и `atlas` не переписываются, Image Asset ID не перевыпускаются; использование нового режима требует явного сохранения и Studio Sync. Переключение не меняет plot pivots и идентификаторы размещений.

Статическая проверка: `test_m382_material_atlas_contract.py`, M381, M371/372, alpha/sync тесты, Luau guard, `verify.py`. Фактическое наложение TextureID и Material проверяется только в Roblox Studio.
