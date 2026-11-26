--!strict
-- Temporary male GP presentation only; authored attack sets remain independent.
local RunService = game:GetService("RunService")
local Policy = {}
function Policy.IsMaleTest(character: Model): boolean
    return RunService:IsStudio() and character:GetAttribute("GameplayTestKind") == "player"
        and character:GetAttribute("CharacterArchetype") == "human_male"
end
function Policy.BorrowsLocomotion(character: Model, weaponSet: string): boolean
    return Policy.IsMaleTest(character) and (weaponSet == "2hs" or weaponSet == "dualswords")
end
function Policy.WeaponSet(character: Model, weaponSet: string, slot: string): string
    if slot ~= "attack" and Policy.BorrowsLocomotion(character, weaponSet) then return "1hs" end
    return weaponSet
end
return table.freeze(Policy)
