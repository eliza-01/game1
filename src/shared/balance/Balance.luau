--!strict
local Registry = require(script.Parent:WaitForChild("BalanceRegistry"))
local Balance = {}
Balance.Rules = Registry.rules
Balance.Test = Registry.test
Balance.Weapons = Registry.weapons
Balance.Monsters = Registry.monsters
Balance.MaxLevel = #Registry.levels
Balance.Armors = Registry.armor
Balance.Grade = require(script.Parent:WaitForChild("EquipmentGrade"))
local weapons: {[string]: any} = {}
local monsters: {[string]: any} = {}
local monstersByType: {[string]: {[number]: any}} = {melee={}, ranged={}}
local armor: {[string]: any} = {}
local thresholds: {number} = {0}
for _, row in ipairs(Registry.weapons) do weapons[row.id] = row end
for _, row in ipairs(Registry.monsters) do
    monsters[row.id] = row
    monstersByType[row.type][row.level] = row
end
for _, row in ipairs(Registry.armor) do armor[row.id] = row end
for level = 2, #Registry.levels do
    thresholds[level] = thresholds[level - 1] + Registry.levels[level - 1].xpNext
end
function Balance.NormalizeXP(value: any): number
    local xp = tonumber(value)
    if not xp or xp ~= xp or xp == math.huge or xp == -math.huge then return 0 end
    return math.clamp(math.floor(xp), 0, thresholds[#thresholds])
end
function Balance.NormalizeGold(value: any): number
    local gold = tonumber(value)
    if not gold or gold ~= gold or gold == math.huge or gold == -math.huge then return 0 end
    return math.clamp(math.floor(gold), 0, 9007199254740991)
end
function Balance.LevelForXP(value: any): number
    local xp = Balance.NormalizeXP(value)
    for level = #thresholds, 1, -1 do
        if xp >= thresholds[level] then return level end
    end
    return 1
end
function Balance.Level(level: number): any
    return Registry.levels[math.clamp(math.floor(level), 1, #Registry.levels)]
end
function Balance.Threshold(level: number): number
    return thresholds[math.clamp(math.floor(level), 1, #thresholds)]
end
function Balance.WeaponForModel(slug: string, weaponType: string): any?
    local row = weapons[Registry.weaponBindings[slug] or ""]
    return if row and row.type == weaponType then row else nil
end
function Balance.Weapon(id: string): any?
    return weapons[id]
end
function Balance.Monster(id: string): any?
    return monsters[id]
end
function Balance.MonsterAt(level: number, kind: string): any?
    local rows = monstersByType[kind]
    return if rows then rows[level] else nil
end
function Balance.WeaponDamage(row: any, upgrade: number): number
    local rank = math.clamp(math.floor(upgrade), 0, Registry.rules.maxUpgrade)
    return math.floor(row.damage * (1 + rank * Registry.rules.upgradePercent / 100) + 0.5)
end
function Balance.MonsterForModel(slug: string): any?
    return monsters[Registry.monsterBindings[slug] or ""]
end
function Balance.Armor(id: string): any?
    return armor[id]
end
return table.freeze(Balance)
