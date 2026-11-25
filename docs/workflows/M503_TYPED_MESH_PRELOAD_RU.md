# M503 · Typed Mesh Preload

M501 передавал ContentProvider:PreloadAsync список строк MeshId. Roblox трактует строки как изображения, что приводит к Asset type does not match requested type. M503 передаёт типизированные MeshPart (временная копия без текстуры/дочерних объектов), SpecialMesh или Decal. Кэш разделён по типам. Успех только по callback Success; ошибки не кэшируются как успех, повтор ограничен cooldown. Исходные модели не меняются. SurfaceAppearance использует отдельные обработанные PBR texture packs, которые PreloadAsync не поддерживает. Обычные текстуры по-прежнему запрашиваются независимо от геометрии. Сохранены ограничения параллельности, таймаут и запрет замены preview при отсутствии геометрии. Успешный запрос не гарантирует постоянное присутствие ресурса в памяти renderer.

Документация: https://create.roblox.com/docs/reference/engine/classes/ContentProvider ; https://devforum.roblox.com/t/contentproviderpreloadasync-and-preload-update/49069

Проверка: Rojo Sync, новый Studio Play, дождаться обоих персонажей, переключить каждую причёску, войти в мир. В Client Command Bar можно запустить system/verify/studio_typed_mesh_preload_m503.luau для проверки реальных опубликованных MeshPart. При ошибках теперь выводится тип, ID и конкретный статус или отсутствие callback.

Отдельно: ошибки двух составных LOD1 (blossom_tree_02 / mid_tree_02) не вызваны предзагрузкой персонажей. Существующий контракт LOD1 требует одного MeshPart; поддержка нескольких компонентов потребует отдельной согласованной доработки шаблонов и потребителей Studio/Runtime. Не ослаблять проверку count и не отбрасывать второй меш.
