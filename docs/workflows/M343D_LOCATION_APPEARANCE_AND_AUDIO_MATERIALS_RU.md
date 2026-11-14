# M343D — Location Assets: Atlas или Roblox Material + Color

База: M343B1A. Real Estate, Collision Blueprint Capture, физические Parts,
пивоты Blender и существующие экземпляры Workspace не меняются при установке.

## При регистрации

1. Выбрать FBX, имя и категорию.
2. Указать `Appearance source`:
   - `Roblox Material + Color` (новое значение по умолчанию: `SmoothPlastic`, `#FFFFFF`).
     Указать `Visual Roblox material` из поддерживаемых материалов BasePart и цвет.
     Изображение/атлас не требуется. Публикуется только Model.
   - `Texture Atlas` — существующая схема PNG/JPG / Atlas Registry.
     Для атласного ассета Image ID по-прежнему требуется перед Studio Sync.
3. Указать независимый `Object material · interaction sounds`.
   Это семантический ключ звука (soundFamily), он не устанавливает Roblox
   `MeshPart.Material`. Поле `surfaceMaterial` сохранено для совместимости.
4. Register → Publish Model (если ещё не опубликована) → Place / Studio Sync.

## Совместимость

- Старые ассеты по умолчанию `appearanceMode=atlas`; их Model ID и Image ID не меняются.
- Материальный ассет считается `PUBLISHED` при актуальной Model без Image ID.
- Изменение Visual Material/Color или звукового материала не публикует FBX повторно.
- При `material` режиме Studio устанавливает материал и Color3, очищает TextureID
  и SurfaceAppearance. При возврате к Atlas используется выбранный вариант и
  Studio восстанавливает TextureID/SurfaceAppearance через явный Sync.
- Для переключения Material → Atlas сначала открыть вкладку Texture · atlas
  у существующего ассета, затем выбрать `Use selected atlas`, опубликовать его
  при необходимости и выполнить Studio Sync.
- Привязка звуков к `soundFamily` остаётся логической. Фактическое
  воспроизведение звуков определяется игровым sound-движком отдельно.
- `Air` и `Water` — Terrain-only, поэтому отсутствуют в списке BasePart.
  `ForceField` отображается, но недоступен без текстуры: согласно документации
  Roblox, для него необходим MeshPart с корректной UV и TextureID.
- Material свойство Roblox также может задавать физические свойства BasePart
  (трение/плотность при отсутствии CustomPhysicalProperties); это встроенное
  поведение движка, независимое от логического soundFamily.

## Миграция / безопасность

- Аддитивная SQLite-миграция: `appearance_mode`, `visual_material`, `visual_color`.
- Перед ALTER TABLE создаётся backup в `.control-center/backups`.
- Старые строки автоматически остаются atlas; миграция не удаляет их атласы.
- Старые записи аудита принимаются; новые события `appearance` фиксируют
  изменение материала и цвета без модификации таблиц MySQL.
- Текущие размещения в Workspace при установке не изменяются. Изменение
  внешнего вида в Studio требует отдельного пользовательского Sync.
- При первой проверке после установки необходимо убедиться, что Game1Bridge,
  Plots, Place Registry и обычная Atlas-публикация запускаются.

## Установка

1. Закрыть Roblox Studio, остановить Control Center.
2. Сделать резервную копию Place и текущего проекта.
3. `git -c core.autocrlf=true apply --check <patch>`; затем apply.
4. `python -m unittest discover -s system/verify -p "test_location_material_registration_m343d.py" -v`.
5. `python system/verify/verify.py` и `python system/studio-plugin/validate_luau.py`.
6. `./system/studio-plugin/install.ps1`; запустить Control Center заново,
   перезапустить Roblox Studio. Rojo не требует ручного перезапуска.

## Приёмка Studio (выполняется пользователем на настоящем Place)

- Register материал без PNG/JPG → Publish Model → размещение видит материал/цвет.
- Edit материала/цвета опубликованного Location Asset → Find / Sync →
  размещения обновляют материал/цвет без изменения Mesh ID, pivot, placement ID.
- Edit звукового `surfaceMaterial` → Sync → обновляется только ключ soundFamily;
  визуальный материал остаётся прежним.
- Atlas asset (включая alpha) после Sync сохраняет ColorMap/AlphaMode.
- Переключение Atlas → Material → Atlas на тестовой модели не оставляет старую
  SurfaceAppearance при material и восстанавливает выбранный atlas при обратном Sync.
- Plots и Place Registry загружаются; Collision Capture по Model + Parts работает.

Скриптовые тесты не заменяют реального запуска в Studio. M343C (Collision
Blueprint Part replication for placed Location Assets) реализуется отдельно.
