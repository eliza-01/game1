local CharacterStatsConfig = {}
CharacterStatsConfig.Default = table.freeze({
    Level = 1,
    MaxHP = 100,
    Damage = 10,
    Defense = 0,
    AttackSpeed = 100,
    RunSpeed = 50,
})
return table.freeze(CharacterStatsConfig)
