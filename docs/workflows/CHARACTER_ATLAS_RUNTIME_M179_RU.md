# M179 — Character Assembly: применение опубликованных атласов

Дата: 2026-10-31. База: `game1_diag_2026-10-31_17-57-28.zip`.

## Симптом и причина

После успешного назначения Image Asset `130840873415092` части `newborn_upper` у
`human_male` сборка прерывалась ошибкой
`AssetService:CreateSurfaceAppearance: ColorMap value should be an EditableImage Content`.
`CreateSurfaceAppearanceAsync` не принимает `Content.fromUri("rbxassetid://...")` как
`ColorMap`: этот factory рассчитан на `EditableImage Content`. Это не ошибка
публикации атласа и не ошибка скелета.

## Исправленный контракт

- `CharacterAssemblyBuilder` только собирает 8 частей и делегирует наложение
  атласа `CharacterAtlasBinder.Apply(mesh, part.atlas_image_id)`.
- Пустой Image Asset ID означает **без runtime override**: оставляем оригинальный
  материал части как опубликовано в Model Asset.
- Непустой Image Asset ID должен быть положительной десятичной строкой. Сначала
  присваиваем `MeshPart.TextureID = "rbxassetid://" .. imageId`, затем убираем
  исходный `SurfaceAppearance`, который иначе перекрывает `TextureID`.
- Ни `AssetService:CreateSurfaceAppearanceAsync`, ни `EditableImage`, ни записи в
  `SurfaceAppearance.ColorMap` в игровом runtime нет.
- Перепубликация Image Asset/Model Asset, изменение recipe, fingerprint,
  реестра, asset IDs и базы SQLite **не нужны**.

Предел: `TextureID` накладывает обычную UV-текстуру, но не переносит PBR-карты,
авторский `AlphaMode=Transparency` и другие свойства исходного `SurfaceAppearance`.
Если конкретная часть нуждается в них, требуется отдельная схема подготовки
материалов в Studio/публикуемых моделях. Для остальных частей без atlas override
их импортированные `SurfaceAppearance` сохраняются.

## Регрессия

Автоматически: `python -W error::ResourceWarning -m unittest discover -s system/verify -p "test_*.py" -q`,
`python system/verify/verify.py`, `python system/studio-plugin/validate_luau.py`.

В Studio Play:
1. Обновить Rojo, перезапустить Play (сбросит кэш собранных моделей).
2. Нажать Accept Loadout для `human_male`. Ошибка
   `CreateSurfaceAppearance` не должна возникать, новая модель появляется.
3. В `Workspace` найти у персонажа MeshPart с `CharacterPartSlot=upper`:
   `TextureID` должен быть `rbxassetid://130840873415092`, а
   `SurfaceAppearance` у этой части — отсутствовать.
4. Другие семь частей по-прежнему на месте; их внешний вид не изменяется,
   кроме иных явно назначенных атласов. Проверить взгляд со всех сторон,
   движения и волосы. Для теста binder можно запустить
   `system/verify/studio_character_atlas_binding_m179.luau` в Command Bar
   (Studio Play, контекст Server).
5. При ошибке проверить `Player.CharacterLoadError` и логи. Никаких повторных
   регистраций или публикаций не требуется.
