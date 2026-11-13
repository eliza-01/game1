# M194 · Characters · Rigless Hair / Pivot → hair_mount

## Проблема

Старый `character_components_fbx.py` требовал у **каждого** mesh один
`Armature Modifier` и нормализованные веса. Цельная `hair_03_common` без
скиннинга отвергалась при Inspect, хотя в контракте персонажа цельные
причёски предусмотрены как независимые жёсткие элементы.

## Текущий runtime (обновлён M336)

Эта документация описывает происхождение формата Pivot Hair в M194.
Действующая система закрепления **M336**: `BoneModelMount` плюс
`BoneMountedAttachmentController`, общий с оружием. У rigid-парика все
MeshPart закреплены `Anchored`, модель перемещается целиком без
`RigidConstraint` и без `CharacterHairExtraWeld`. Ниже приведён
исходный исторический контракт M194, не отдельный runtime.

## Контракт

- Единственный исключённый из обязательного скиннинга слот:
  `hair_<NN>_male|female|common`.
- Для `hair_*` без Armature Modifier: объект имеет ненулевую геометрию,
  **нулевые deform weights**; у главного рига обязательно есть `hair_mount`.
- Blender Object Origin/Pivot причёски должен быть авторски настроен как
  точка, совпадающая с `hair_mount` после сборки. Геометрический центр не
  используется как крепление.
- Отдельный FBX включает только mesh, не включает риг персонажа и не
  создаёт искусственные веса или bones. Трансформация Object Origin
  сохраняется при временном отделении от parent для экспорта.
- Метаданные публикации: `attachment='hair_mount'`, `attachment_mode='pivot'`,
  `armature=''`, `skeleton=[]`, `used_bones=[]`.
- В рецепте `attachment_mode='pivot'` указывает `CharacterAssemblyBuilder`
  совместить `mesh:GetPivot()` с `hair_mount.WorldCFrame` посредством
  `mesh:PivotTo(target.WorldCFrame)` и построить существующий RigidConstraint.
  `MeshPart.CFrame` не является заменой pivot (учитываем `PivotOffset`).
- Для скелетной причёски остаётся прежняя схема со своим
  `hair_XX_<gender>_armature`, socket-биндом и root Bone; прежние рецепты
  без `attachment_mode` читаются как `socket`.
- Для других слотов требование модификатора и 1–4 нормализованных весов
  остаётся. Регистрируемые модели, Asset ID и алгоритм публикации не меняются.

## Применение

1. Обновить исходный FBX с `hair_03_common` и основным ригом,
   содержащим `hair_mount`. В Blender проверить Object Origin причёски.
2. **Characters → Rig & Parts → Inspect**: рядом с причёской появится
   `rigid pivot → hair_mount`.
3. Подтвердить замену одноимённой части, если она ранее публиковалась;
   пройти Register → Queue → Publish, затем выбрать её в assembly-рецепте.
4. Запустить Roblox Studio Play и проверить положение волос при
   повороте/наклоне головы, а также при смене анимаций. Если pivot создан
   неправильно в Blender, фиксировать нужно его на исходном ассете, а не
   константой смещения в runtime.

## Проверки и ограничения

Контрактная проверка использует fake-bpy с настоящим вызовом `main` для
Inspect, проверяет mesh-only extraction и регистрацию. Реальный Blender FBX
export, Roblox Open Cloud import и Roblox rigid attachment требуют Play-теста;
они не эмулируются Python. Предыдущие скелетные причёски совместимы.
