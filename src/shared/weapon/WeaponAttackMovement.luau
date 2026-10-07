local WeaponRegistry = require(script.Parent:WaitForChild("WeaponRegistry"))

local WeaponAttackMovement = {}

local FALLBACK = table.freeze({
    weaponType = "hands",
    animationSet = "hands",
    locomotionMode = "Run",
    runSpeedMultiplier = 1,
})

local function normalizedMode(value: any): string
    return if string.lower(tostring(value or "")) == "walk" then "Walk" else "Run"
end

function WeaponAttackMovement.Resolve(weaponTypeValue: any): any
    local weaponType = string.lower(tostring(weaponTypeValue or ""))
    local source = WeaponRegistry.attackMovementByType and WeaponRegistry.attackMovementByType[weaponType]
    if not source then
        return FALLBACK
    end
    return {
        weaponType = weaponType,
        animationSet = string.lower(tostring(source.animationSet or weaponType)),
        locomotionMode = normalizedMode(source.locomotionMode),
        runSpeedMultiplier = math.clamp(tonumber(source.runSpeedMultiplier) or 1, 0, 2),
    }
end

function WeaponAttackMovement.AnimationSetForType(weaponTypeValue: any): string
    return WeaponAttackMovement.Resolve(weaponTypeValue).animationSet
end

function WeaponAttackMovement.LocomotionModeForType(weaponTypeValue: any): string
    return WeaponAttackMovement.Resolve(weaponTypeValue).locomotionMode
end

function WeaponAttackMovement.RunSpeedMultiplierForType(weaponTypeValue: any): number
    return WeaponAttackMovement.Resolve(weaponTypeValue).runSpeedMultiplier
end

return table.freeze(WeaponAttackMovement)
