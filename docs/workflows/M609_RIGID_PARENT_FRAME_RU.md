# M609 · Rigid Parent Frame · KBN-0037-T02

M607 и M608 не прошли визуальную приёмку: отделение экипировки в прыжке, меч NPC не в руке в Idle. Identity child Bone M608 не исправила проблему и удалена. Это не подтверждает конкретную причину дефекта Roblox solver.

До M607 оружие искалось в Visual (fallback ImportedRig/character), волосы — в каноническом rig_carrier. Поза сокета вычислялась как `parent.TransformedWorldCFrame * target.CFrame`, либо `target.WorldCFrame` для top-level, затем применялась authored ориентация. M609 возвращает этот контракт. Если P — animated parent frame, L — authored local socket frame, R — поправка ориентации, G — grip в локальных координатах предмета, то joint endpoints P и G*(L*R)^-1 обеспечивают уравнение item*G = P*L*R. Собственный Transform сокета не участвует. Для top-level endpoint — обычная identity Attachment на MeshPart, одна на часть. Native RigidConstraint остаётся один на предмет. Bow release/Timeline используют endpoint, hair readiness — исходный carrier и постоянный offset. Новых Bone, follower, сетевых запросов или перепубликаций нет.

## Приёмка владельцем (функционально подтверждена)

27.11.2026: владелец сообщил «супер работает в рантайме и на телефоне». KBN-0037-T02 выполнен. Полная матрица ниже и инструментальные замеры не подтверждены отдельным отчётом; A02/T06 остаются открыты. Следующий этап — Performance Profiler; сравнить M605/M609 на одинаковой сцене отдельно от рабочего DEV.

### Матрица оставшейся регрессии и диагностики

1. Rojo Sync, Studio Play. Герой Idle/бег/поворот/прыжок, NPC Idle/бег/атака. Проверить второй клиент, смену оружия, обе руки, лук, compound hair, Character Creation и Timeline. Пересоздать старые сохранённые анимационные стенды.
2. При расхождении выполнить `system/verify/studio_m609_equipment_snapshot.luau` в Command Bar (Client и Server) в наблюдаемом состоянии. Это разовая диагностика, не runtime-модуль. `contract error` — ошибка геометрического контракта; `solver error` — расхождение нативных endpoints; `visual error` — отклонение видимого grip от прежнего сокета. Сохранить лог и не менять FBX/пивоты/корневую физику наугад. Для прыжка использовать паузу симуляции или снимок в момент прыжка. Если контракт верен, а solver не выполняет уравнение, эксперимент RigidConstraint не принят; не добавлять дочерние Bone повторно.
3. Только после Studio-приёмки — DEV Runtime, физический телефон, сравнение CPU/Physics/frame time с M605. Не закрывать A02/T06 по статическим тестам; T02 принят владельцем функционально.
