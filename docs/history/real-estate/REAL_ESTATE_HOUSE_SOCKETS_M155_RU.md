# M155 · House Sockets: stateful padlock, elevator, unified E / F

> **Исторический документ.** Фиксирует состояние на момент указанного этапа; отдельные механизмы могли быть заменены. Действующие контракты: [актуальное ТЗ](../../spec/CURRENT_PROJECT_SPEC_RU.md), [архитектура](../../architecture/CURRENT_ARCHITECTURE_RU.md).


## Input and presentation

- Default interaction is **E** (door, chest, padlock, elevator).
- **F** is reserved only for downward movement in houses with three floors.
- The UI renders actual server-authored E/F actions; on elevator floor 2 it
  can render E and F simultaneously (two lines at one socket).
- Studio House Sockets panel target height: **910 px**, bounded by viewport.

## Padlock (runtime-only, server-authoritative)

- A house with `door_01_padlock_01_socket` initially has the padlock attached.
  `Game1PadlockAttached` on the **house** is its runtime state. Re-registering
  the house doesn't reset it. Houses without that socket are never locked.
- Stub key: **always present**, checked on the server in HousePadlockService.
- E at padlock (attached): remove padlock, hide placeholder, unlock door.
- E at door: can open/close only while unlocked.
- E at padlock (removed): reattach only when door is **closed and stationary**.
  While door is open the padlock prompt is disabled; the server rejects forged
  requests regardless of UI. Placeholder is merely hidden, not duplicated.
- This state is **not persisted** to SQLite. Real key inventory and durable
  ownership need a separate feature in the future.

## Elevators: deterministic routing, real bones only

`HouseElevatorPolicy` is a pure shared floor/key router.
`HouseElevatorService` applies the movement after server validation of source
socket, distance, player life state, target bone and key. No platform movement
animation is implied; current behavior teleports to the destination elevator.

| Authored elevator sockets | At floor 1 | At floor 2 | At floor 3 |
|---|---|---|---|
| 01 only | No destination | — | — |
| 01 + 02 | E → 2 | E → 1 | — |
| 01 + 02 + 03 | E → 2 | E → 3; F → 1 | F → 2 |

- `elevator_02_socket` and `elevator_03_socket` are optional. A third-floor
  offer requires the **actual `elevator_03_socket`** and a contiguous 01–02–03
  sequence. Having only a third-floor spawn bone does **not** enable floor 3.
- `house_floor_03_spawn_01_socket` is optional for independent Studio TP
  debugging, not required for elevator transfer.
- Destination is the authored elevator bone position +3 studs world-Y offset.
  The actor retains its horizontal facing, and controller/velocity are reset.
- World changes to house sockets are reconciled by existing per-house events;
  there is no heartbeat Workspace scan.

## Boundaries and caveats

- No FBX, bone, Blender, door pivot, animation or Studio Sync changes.
- Test with real Studio Play for a two-floor house, a three-floor house, open
  door + padlock, simultaneous E/F elevator prompts, and custom character TP.
- The pre-existing F-only contract tests are updated to the current behavior.
