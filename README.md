# game1

Новый независимый Roblox-проект. Он использует инженерные принципы RobloxLineage, но **не его Place, базы данных или игровую предметную модель**.

## Важно перед запуском

Распакуй проект в отдельную sibling-директорию, например:

```text
E:\RobloxProjects\RobloxLineage
E:\RobloxProjects\game1
```

**Не распаковывай game1 поверх RobloxLineage и не запускай его из папки RobloxLineage.** `bootstrap.ps1` специально откажется работать из такого пути.

`game1` никогда не использует `place/current.rbxl`. Канонический файл нового проекта:

```text
place\game1.rbxl
```

Первичная сборка создаёт минимальную сцену (Baseplate + SpawnLocation) и runtime. После этого Workspace редактируется и сохраняется в Studio: live Rojo синхронизирует код, но не владеет объектами сцены и не возвращает их позиции назад.

## Первый запуск

Из корня `game1`:

```powershell
.\bootstrap.ps1
```

После успешной сборки:

1. Открой **`place\game1.rbxl`** в Roblox Studio.
2. В Rojo plugin подключись к `127.0.0.1:34882`.
3. В отдельном PowerShell из корня `game1` запусти:

```powershell
.\sync.ps1
```

## Основные команды

```powershell
rokit install
.\system\studio-plugin\install-rojo-plugin.ps1
.\system\studio-plugin\install.ps1
.\place\build-place.ps1
.\control-center.ps1
.\sync.ps1
```

- Control Center: `http://127.0.0.1:43820`
- Host agent: `127.0.0.1:43821`
- Rojo: `127.0.0.1:34882`
- Reserved Studio bridge: `127.0.0.1:43137`

Character DB стартует пустой. Roblox Model asset `99674249877653` используется только как временный bootstrap visual, пока в новом Asset Manager не зарегистрирован первый character archetype.

Gameplay baseline: Level 1, HP 100, Damage 10, Defense 0. Формула урона: `max(0, Damage - Defense)`.
