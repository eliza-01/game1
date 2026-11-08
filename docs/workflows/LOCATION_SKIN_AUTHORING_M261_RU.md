# M261 · Location FBX: подготовка skin до канонического экспорта

## Причина

При `Publish and Apply` для `christmas_tree_01` в авторской FBX присутствует
скелет (3 Bone) и skinned visual `christmas_tree_01` (1870 vertices), но
механизм M260 создавал `rig_carrier` и сразу вызывал общий `export_model`.
В отличие от Character, `location_rig_authoring_fbx.py` **не вызывал**
`model_publication.prepare_rig`, поэтому незаполненный/ненормализованный
skin (например, vertex 80) блокировал экспорт до записи новой FBX-ревизии.
Точный вес исходной вершины 80 отсутствует в диагностическом дампе (бинарные
FBX исключены); обнаружено несоответствие последовательностей обработки.

## Владение и контракт

* `blender_rig_carrier.create_rig_carrier` — **один** helper геометрии carrier
  для Character/Location. Новые генераторы и Studio Repair не добавляются.
* `model_publication.prepare_rig` — **один** общий алгоритм нормализации,
  ограничения 4 influences, заполнения пустых вершин ближайшей авторской
  костью и контроля bone coverage. При **явно запущенном** canonical authoring
  он обрабатывает новый FBX-экземпляр в памяти Blender перед экспортом.
* Source FBX на диске остаётся неизменным. Создаётся новая отдельная authored
  FBX с manifest; `services.location_rig_authoring` сохраняет историю/архив и
  регистрирует его как следующую ревизию. `skinPreparation` в JSON-манифесте
  показывает количество заполненных вершин и прочую статистику подготовки.
* `prepare_model_publication_fbx.py` для `geometry_only` (Location) теперь
  **только валидирует** skin до/после экспорта. Никакого изменения веса
  визуального меша во время публикации. Для Character/Weapon режим
  `embedded` продолжает использовать `prepare_rig` как раньше.
* Source rig rest pose и кости проверяются до/после authoring; FBX round-trip
  должен пройти `assert_skin_complete`. При ошибке Open Cloud не вызывается.
* Для статических Location без Bones новый путь не вызывается вообще.
  Atlas ID и существующий Model ID при подготовке не меняются; новый Model ID
  может появиться только при последующем успешном Publish.

## Проверки

`test_location_carrier_skin_authoring_m261.py`: исходная незаполненная вершина,
нормализация и повторяемость общего Character-планировщика, порядок
`create carrier → prepare rig → export → validate round-trip`, отсутствие
повторной нормализации во время публикации Location. Внутри тестов
используется имитация Blender API; реальный FBX round-trip и импорт в Studio
проверяются отдельно на рабочем месте с Blender и Roblox Studio.
