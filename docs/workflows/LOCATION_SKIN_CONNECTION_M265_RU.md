# M265 · Общая связь skinned MeshPart с `rig_carrier`

## Обнаруженный разрыв

M260/M261 переиспользовали **Blender-authoring** от Character, но Studio
`DecoAssetLoader` не собирал физическую связь visual MeshPart с каноническим
`rig_carrier`. В Character эту задачу выполнял `CharacterSkinWeld`. Перечень
Bone в v2 manifest и проверка `rig_carrier` в опубликованной модели **не
доказывают**, что Roblox сможет использовать их для skinning visual.

Особенно опасно, что `DecoAssetPreparation.PreparePlaced` переводит все детали
Location в `Anchored = false`. M263 сохраняет допустимые импортёрские
`Motor6D`, но его нормализация `RootPart` удаляет joints, направленные к
искусственному корню. После этого у visual/COL могут отсутствовать физические
пути к carrier, и при размещении части разделяются.

## Единственный механизм и граница ответственности

- `src/shared/rig/SkinnedMeshConnection.luau` — **один** Luau-механизм для
  Character и Studio-плагина. Сравнивает связанность по `JointInstance`
  (`Motor6D`, `Weld`) и `WeldConstraint` в пределах одной Model; при отсутствии
  пути добавляет один `Weld` с сохранением CFrame (C0 = carrier→part).
  Существующие корректные importer Motor6D не удаляются и не дублируются.
- `CharacterAssemblyBuilder` использует механизм для `CharacterSkinWeld`
  после прежнего выравнивания bind pose и удаления локальных Bone. Порядок
  и валидация Character не меняются.
- `DecoAssetLoader` использует тот же модуль, подключённый в
  `plugin.project.json` напрямую **по тому же исходному пути**. После
  нормализации M263 и проверки SHA-bound manifest он связывает с carrier все
  ещё не соединённые MeshPart: visual (`LocationSkinWeld`) и отдельный COL
  (`LocationRigWeld`). COL остаётся rigid/physics-only, его вершины не получают
  skinning; визуальные веса и Bones из опубликованного FBX не переписываются.
- Непригодные/external joints и меши внутри вложенной Model отклоняются.
  Все операции происходят на *свежем detached asset*, до помещения в Place.
  Нет скрытого изменения старых размещений, исходного FBX или Model/Atlas ID.
- Статические assets не имеют carrier и не проходят bind, а импортёрские
  соединения в уже связанном скелетном rig не заменяются.

## Проверка в Roblox Studio (обязательна)

1. Установить плагин и открыть **копию Place**. Загрузить свежий опубликованный
   `christmas_tree_01` через Studio. Проверить `rig_carrier` с Bone, визуальные
   меши и COL в **одной Model**, и что каждая часть связана с carrier
   импортёрским Motor6D/цепочкой joints или одним Location*Weld.
2. Создать новое размещение. Все части получают `Anchored=false`, но visual
   и COL остаются одной физической сборкой. Проверить физику, texture, pivot,
   ScaleTo и сохранение на диск.
3. Изменить `Bone.Transform` тестовой ёлки. Убедиться, что visual
   деформируется, а rigid COL не деформируется (обычная граница Roblox skinning).
   Вернуть Transform. При наличии вложенных Model / необычных joints загрузка
   должна завершаться ошибкой, не изменяя Place.
4. Повторить с импортированным Motor6D (никаких дублирующих Weld), с
   нормализованным RootPart, затем проверить Sync одного старого размещения,
   Undo, Save/Reopen и Play. **Не запускать Sync All до этой проверки**.
5. Проверить статический `bush_02`: отсутствие carrier и LocationSkinWeld,
   никакой перепубликации или смены Atlas ID.

Статические тесты проверяют исходники, единый путь модуля и порядок вызовов;
без Roblox Studio нельзя утверждать, что деформация визуального MeshPart
при реальном Open Cloud импорте подтверждена.
