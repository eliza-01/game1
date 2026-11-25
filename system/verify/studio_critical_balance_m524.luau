-- Server Command Bar during Studio Play. Detached model; no player state mutation.
local shared = game:GetService("ReplicatedStorage").Game1Shared
local server = game:GetService("ServerScriptService").Game1Server
local Balance = require(shared.balance.Balance)
local Critical = require(shared.balance.CriticalStats)
local Stats = require(server.character.CharacterStatsService)
local Loadout = require(server.dev.GameplayTestLoadout)
local character = Instance.new("Model")
local function close(actual, expected)
    assert(math.abs(actual - expected) < 1e-6, ("%.4f ~= %.4f"):format(actual, expected))
end
local ok, err = pcall(function()
    local base = Balance.Rules.critChance
    local cap = Balance.Rules.maxCritChance
    local multiplier = Balance.Rules.critMultiplier
    Stats.Initialize(character, {}, 1)
    close(character:GetAttribute("CritChance"), math.min(base, cap))
    for _, weapon in ipairs(Balance.Weapons) do
        Stats.ApplyModifiers(character, {CritChance=weapon.critChance-base})
        close(character:GetAttribute("CritChance"), math.min(weapon.critChance, cap))
        Stats.SetModifierSource(character, "gameplay-test-critical", {CritChancePercent=50,CritChanceFlat=3,CritMultiplier=3-multiplier})
        close(character:GetAttribute("CritChance"), math.min(cap, weapon.critChance*1.5+3))
        close(character:GetAttribute("CritMultiplier"), 3)
        -- Replacing the source must not stack.
        Stats.SetModifierSource(character, "gameplay-test-critical", {CritChancePercent=200,CritChanceFlat=20})
        close(character:GetAttribute("CritChance"), math.min(cap, weapon.critChance*3+20))
        Stats.ClearModifierSource(character, "gameplay-test-critical")
        close(character:GetAttribute("CritChance"), math.min(weapon.critChance,cap))
        close(character:GetAttribute("CritMultiplier"), multiplier)
    end
    Stats.ApplyModifiers(character, {})
    close(character:GetAttribute("CritChance"), math.min(base,cap))
    for _, bad in ipairs({-1, 201, math.huge, 0/0, "50"}) do
        assert(not Critical.ValidateTest(bad, 0, 2))
    end
    assert(not Critical.ValidateTest(0,21,2))
    assert(not Critical.ValidateTest(0,0,5.01))
    local request = {level=1,upgrade=0,weapon="",armor=Balance.Armors[1].id,critPercent=50,critFlat=3,critMultiplier=3}
    assert(Loadout.Validate(request))
    request.critFlat=21
    assert(not Loadout.Validate(request))
end)
character:Destroy()
assert(ok, err)
print("[M524] critical stats / modifier replacement / input validation passed")
