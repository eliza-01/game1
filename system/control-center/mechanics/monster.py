"""Shared monster lifecycle and AI documentation, not per-asset script claims."""
from .house import card

ITEMS = [
    card('monster-spawn-lifecycle', 'Монстры · популяция, смерть, respawn', 'Сервер',
         'Авторские spawn records, maxAlive, индивидуальный цикл смерти и очередной respawn.',
         ['MonsterSpawnRegistry.records', 'MonsterRegistry.monsters'], [
             {'title': 'Работает в исходниках', 'lines': [
                 'MonsterPopulationController резервирует места maxAlive и планирует respawn отдельно для каждого погибшего монстра.',
                 'MonsterSpawnerService собирает риг, hitbox, анимации, wandering и death lifecycle; ресурсы экземпляра очищаются при release.',
             ]},
             {'title': 'Недостающее / проверка', 'lines': [
                 'Время смерти, очередь respawn, HP и положение живой популяции не сохраняются между серверами; при перезапуске популяция создаётся заново из spawn registry.',
                 'Проверить Runtime Place и StreamingEnabled: несколько одновременных смертей, maxAlive, задержки, исключение повторного рождения и cleanup.',
             ]},
         ], ['monster-spawner', 'monster-population', 'monster-death', 'monster-spawns', 'monster-registry']),
    card('monster-ai-pursuit', 'Монстры · aggro, pursuit, return', 'Сервер',
         'Агрессия, атака и возвращение к исходной точке управляются серверным AI.',
         ['MonsterAggressive', 'pursuitRadiusStuds'], [
             {'title': 'Работает в исходниках', 'lines': [
                 'MonsterAIService использует ActorHomeLeash и ActorDamageSignals: после таймаута без урона или выхода за радиус преследования начинает Return.',
                 'Pursuit radius — настройка вида из MonsterRegistry; spawn radius нужен для появления/блуждания и не ограничивает саму погоню.',
                 'Полученный урон во время Return может снова запустить боевое преследование.',
             ]},
             {'title': 'Недостающее / проверка', 'lines': [
                 'Threat, цель, фаза атаки, положение во время Return и таймер без урона живут только на одном сервере и не восстанавливаются.',
                 'Проверить путь по Terrain и препятствиям, границу pursuit от spawn, два вида с разными настройками и смену цели между игроками.',
             ]},
         ], ['monster-ai', 'actor-home', 'monster-target', 'monster-nav', 'monster-registry']),
    card('monster-attack-visuals', 'Монстры · атака, анимации, эффекты', 'Бой',
         'Серверная боевая механика и клиентская визуализация движения и hit feedback.',
         ['MonsterAnimationRegistry', 'EntityHitboxService'], [
             {'title': 'Работает в исходниках', 'lines': [
                 'MonsterAttackExecutor исполняет атаку; общий DamageService и EntityHitboxService обрабатывают урон и боевые границы.',
                 'MonsterAttackLocomotionController визуализирует анимации, MonsterDeathLifecycle ведёт смерть и освобождение слота.',
             ]},
             {'title': 'Недостающее / проверка', 'lines': [
                 'Боевой результат не создаёт подтверждённого постоянного loot/XP/quest transaction; выдача наград требует отдельного серверного контракта.',
                 'Нужна Studio Play проверка сетевой синхронизации атак, headshot/OBB, анимационных переходов и повторного появления.',
             ]},
         ], ['monster-attack', 'monster-client-attack', 'monster-death', 'damage-service', 'entity-hitbox']),
]
