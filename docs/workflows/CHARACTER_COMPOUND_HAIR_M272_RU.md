# M272 · Составные жёсткие причёски и цвета

Один Character component `human_female_m004_hair` публикуется как **один Roblox Model asset** с несколькими MeshPart:

```text
human_female_m004_hair                # root, единственный hair_mount
human_female_m004_hair_extra_01       # непереиспользуемая часть, канал extra_01
human_female_m004_hair_extra_02       # ещё одна часть, канал extra_02
```

## Blender / FBX

- Root и extras — отдельные Mesh Objects в одной сцене/FBX. Не объединять, не делать скининг и Armature modifier на этих объектах.
- Origin root — авторская точка `hair_mount`. Extras могут иметь **свои Origin**: Blender-экспорт сохраняет их мировые transform, а Roblox сохраняет их относительную позицию от root. Подгонять все Origin к root не требуется.
- Применять Rotation/Scale согласованно (без случайного перемещения геометрии), экспортировать **только root и extras**. `dummy_04` не экспортировать.
- Предпочтительный FBX — один root + его `extra_XX` и без armature. Такой файл можно Inspect/Register только если в каталоге уже есть rig profile (`human`) с `hair_mount`.
- Можно экспортировать общий `human_armature` вместе с причёской, но он не нужен и не публикуется повторно при самостоятельной регистрации hair.
- `extra_XX` не появляется отдельной строкой каталога, не получает отдельный Model Asset ID, не назначается в Armor и не заменяется отдельно. Любая правка extra меняет revision всей hair.
- Номера `extra_01` .. `extra_99` уникальны внутри причёски. Нельзя публиковать осиротевшие extras или extras с деформационными весами.

## Roblox

Builder проверяет фактический список MeshPart против metadata из опубликованной FBX. Root получает `CharacterMount` и крепится к `hair_mount`. Все extras входят во внутреннюю модель `CharacterHairComponent`, связываются с root `CharacterHairExtraWeld`. Клиентский `HairAttachmentController` перемещает **всю** `Model:PivotTo`, а не только один MeshPart. Каждый extra сохраняет свой локальный transform и PivotOffset.

Настройка цвета независима от геометрии и не создаёт копии MeshPart. `hair_colors` в Character recipe:

```json
{"primary":"#5A321E","extra_01":"#D43B68"}
```

Color-контракт разрешает только реальные каналы опубликованной модели. Неизвестные каналы и невалидные hex отклоняются. `HairColorBinder.Apply()` доступен для повторного окрашивания модели без перестройки персонажа. Если нет `SurfaceAppearance`, используется `MeshPart.Color`. Если есть SurfaceAppearance, используется `SurfaceAppearance.Color` для tint нейтральной ColorMap (Roblox API). Для произвольных цветов рекомендуется нейтральный белый материал/texture, без заранее заданной пигментации.

Сохранение startup/debug сборки поддерживает отдельные color pickers, создаваемые по опубликованным extras. Отдельный игровой экран смены цвета не вводится: он сможет вызвать ту же `HairColorBinder` после интеграции профиля персонажа.

## Проверки в Studio

1. Опубликовать FBX с root + extra_01, подтвердить: один Model asset, два MeshPart.
2. В Debug Assembly выбрать `human_female_m004_hair`, задать два цвета.
3. Проверить Play: бант следует за головой при повороте/движении, не смещается от своего Pivot.
4. Перекрасить модель через `HairColorBinder.Apply(group, {primary="#...",extra_01="#..."})` без пересборки.
5. Перепубликовать hair с добавленным extra_02: новую ревизию выбирать через resolver; старый готовый рецепт с прежней ревизией не должен silently изменяться.

Blender/Roblox Studio Play требуют теста в пользовательской среде: статические тесты не доказывают точность FBX pivot и движение в Studio.
