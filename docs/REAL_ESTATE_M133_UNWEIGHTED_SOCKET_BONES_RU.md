# M133 · Real Estate: восстановление невзвешенных сокетов в Studio

## Проблема

Roblox Open Cloud сохраняет опубликованный `door` Model Asset, но его загрузка
в Roblox Studio может не содержать дочерних `Bone`, не влияющих на вершины.
Такое поведение нельзя исправить одним наличием узлов в FBX, и M132 лишь
снимал блокировку Studio Sync, оставляя точки недоступными.

## Решение

1. `RealEstateStudioSync` передаёт **зарегистрированные авторские**
   `matrixLocal` и `parent` из `skeleton_json` как `authoredBones`.
   Повторный анализ FBX, загрузка в Open Cloud и миграция SQLite не требуются.
2. `StudioRealEstateSocketRecovery` обнаруживает существующие Roblox `Bone`
   внутри исходного MeshPart и восстанавливает **только отсутствующие**
   дочерние `*_socket` как настоящие `Bone` под выжившим импортированным
   родителем. Их `CFrame` = `parentRest:ToObjectSpace(socketRest)`.
3. Запрещены синтетические позиции без авторской матрицы или импортированной
   родительской кости; запрещены добавочные веса, изменение `Bone.Transform`,
   перепубликация FBX и изменение `Image Asset ID`.
4. Затем штатная `StudioRealEstateRigValidation.Verify` проверяет итоговый
   фактический риг **до** замены существующего ServerStorage-шаблона.
5. `Game1RecoveredRealEstateSockets` хранит JSON-массив восстановленных имён
   вида `door/door_01_handle_inside_socket`. Каждый восстановленный Bone помечен
   атрибутом `Game1RecoveredFromFBXRestPose = true`.

## Непосредственно для house_level4_01

В сохранённом `skeleton_json` имеются rest-матрицы всех четырёх костей
`door_armature`: hinge и трёх дочерних сокетов. При наличии импортированного
`door_01_hinge_socket` в Studio три исчезнувших сокета восстанавливаются при
**обычном Sync Studio**, без новой публикации модели.

## Границы достоверности

- Эти Bone **восстанавливаются внутри Studio-шаблона**, а не внутри Roblox
  Model Asset на серверах Roblox. Если загрузить Model Asset другим способом,
  понадобится тот же адаптер сборки.
- При сохранённой parent-Bone локальные матрицы из Blender задают относительное
  положение. Окончательное совпадение осей с реальным Roblox FBX-импортом
  нужно проверить в Studio по расположению ручек и замка: автономные тесты
  не могут проверить преобразование координат платформы.
- Если весь риг без весов был удалён и у сокетов **нет ни одной оставшейся
  родительской Bone**, система не угадывает их координаты и оставляет
  предупреждение. Для такого случая нужна отдельно калиброванная опора.
- Контроллер двери по-прежнему вращает `DoorAssembly` целиком через `PivotTo`,
  не `Bone.Transform`.

## Проверка после M133

1. Закрыть Studio, установить M133 и плагин, перезапустить Studio.
2. В Real Estate выбрать `house_level4_01` и нажать `Sync Studio`.
3. В `ServerStorage/real_estate/house_level4_01/model/house_level4_01`
   проверить `Game1MissingRealEstateSockets` (`[]`) и
   `Game1RecoveredRealEstateSockets` (три записи с префиксом `door/`).
4. Внутри `DoorAssembly/DoorRig/door` должны находиться
   `door_01_hinge_socket` и три его дочерних `Bone`. У дочерних проверить
   `Game1RecoveredFromFBXRestPose=true` и визуальные позиции.
5. Проверить, что положение, веса, Model/Image Asset IDs не изменились.
