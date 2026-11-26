local Balance = require(script.Parent.Parent:WaitForChild("balance"):WaitForChild("Balance"))
local CharacterStatsConfig = {}
CharacterStatsConfig.RegenerationHPPerSecond = 0
CharacterStatsConfig.Default = table.freeze({
    Level = 1,
    MaxHP = Balance.Level(1).hp,
    Damage = Balance.Rules.baseDamage,
    Defense = 0,
    AttackSpeed = Balance.Rules.baseAttackSpeed,
    RunSpeed = Balance.Rules.baseRunSpeed,
    CritChance = Balance.Rules.critChance,
    CritMultiplier = Balance.Rules.critMultiplier,
})
return table.freeze(CharacterStatsConfig)
