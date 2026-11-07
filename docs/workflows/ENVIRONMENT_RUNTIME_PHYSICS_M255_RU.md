# M255 · Runtime Location physics без Plugin-only свойств

`EnvironmentAssetService` закрепляет размещённые Location Assets и применяет
runtime collision-флаги. `CollisionFidelity` при этом не записывается: Roblox
разрешает изменять это свойство только Plugin/OpenCloud-контексту, а его
авторское значение уже сохранено Studio pipeline.

До M255 исключение на первой модели прерывало старт сервиса. Незакреплённые
визуальные MeshPart `stone_fence_01` падали ниже `FallenPartsDestroyHeight`,
тогда как закреплённые COL оставались в Place. Runtime теперь использует
`ApplyLocationModelRuntime`; Studio plugin продолжает использовать прежний
`ApplyLocationModel` и остаётся единственным владельцем `CollisionFidelity`.
