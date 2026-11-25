# M506 · Удаление Training Dummy и старого LOD probe

TrainingDummyService и его регистрация удалены. Общие хитбоксы, урон, NPC,
монстры и Character Test Stand не меняются.

Старый Game1LodProbeClient уже исключён из Rojo в M434; сохранённый Place
может всё ещё содержать standalone LocalScript вне управляемого Game1Client.

1. Остановить Play, синхронизировать Rojo.
2. В Studio Edit mode выполнить содержимое
   `system/verify/studio_retired_debug_cleanup_m506.luau` в Command Bar.
   Удаляются только одноимённые скрипты в StarterPlayerScripts и модель
   game1TrainingDummy непосредственно в Workspace. Действие можно отменить.
3. Сохранить authoring Place. Перед новой Runtime сборкой заново сохранить
   XML source. Preflight проверяет отсутствие этих двух устаревших экземпляров.

Скрипт очистки не является частью игрового runtime и не запускается автоматически.
