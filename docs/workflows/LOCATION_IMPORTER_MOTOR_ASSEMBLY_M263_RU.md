# M263 · Нормализация importer assembly опубликованного Location rig

## Причина

Roblox Importer может добавить `Motor6D` при импорте многокомпонентного
skinned FBX, даже если исходный FBX содержит только Mesh, Armature и Bones.
Поэтому наличие любого `Motor6D` не доказывает, что публикация использует
старую структуру с `RootPart`. Прежняя проверка останавливала Studio Find до
анализа размещённых legacy-моделей.

## Контракт

- Авторский FBX и итоговый размещённый child rig не могут содержать `RootPart`.
  Если `LoadAssetAsync` добавил ровно один невидимый импортёрский `Part`
  `RootPart` вокруг skinned v2-публикации, отдельный Location-only normalizer
  удаляет его только на свежем detached clone до валидации и размещения.
- Normalizer переносит только исходные root Bones под настоящий опубликованный
  `rig_carrier`, удаляет только проверенные joints к importer RootPart и
  доказывает неизменность Model pivot, MeshPart `CFrame`/`Size`, Bone world/rest
  frame и pose `Transform`. Неизвестный child/joint или внешний endpoint
  останавливает операцию до изменения Place.
- Импортёрские `CanCollide/CanQuery` defaults на прозрачном RootPart допустимы
  только при наличии отдельного manifest-подтверждённого COL MeshPart. Без COL
  normalizer закрывает операцию до изменения Place.
- Static-публикация не может содержать `Motor6D`.
- В skinned v2-публикации допустим только importer `Motor6D`, у которого
  `Part0` и `Part1` — разные `MeshPart` из SHA-bound manifest этой публикации
  и оба находятся внутри загруженной Model.
- Параллельные joints одной пары и циклическая assembly отклоняются.
- Studio не удаляет, не заменяет и не синтезирует допустимый joint. Полная
  legacy-миграция M262 переносит опубликованный child rig через
  `StudioManagedRigSwap`, сохраняя корневую Model и её placement transform.
- Внешние ссылки, отсутствующие endpoints, `Part`, которого нет в manifest,
  и неизвестные joints остаются fail-closed до изменения Place.

M263 уточняет запреты `RootPart`/`Motor6D` из M256 на основании фактического
поведения Roblox Importer. Исходный FBX не переписывается, immutable Model Asset
не изменяется, а Studio не синтезирует геометрию. Авторский `rig_carrier`, Bone
manifest, immutable publication history и явный scoped Sync не меняются.

## Проверка в Studio

На резервной копии Place выполнить Find для `christmas_tree_01`: публикация
должна загрузиться, а восемь MeshPart должны отображаться как четыре legacy
размещения. Затем мигрировать один экземпляр и проверить сохранение Model
pivot/scale, визуального `CFrame`/`Size`, Bones, COL, Undo и Save/Reopen. Только
после этого разрешать групповую миграцию оставшихся экземпляров.
