--!strict
-- Studio GP only: an absent authored melee timeline must not block stat testing.
local RunService = game:GetService("RunService")
local Cadence = require(script.Parent:WaitForChild("CharacterAttackCadence"))
local Fallback = {}
Fallback.ClipId = "gp_melee_timing_only"
function Fallback.Allowed(character: Model): boolean
    local kind = tostring(character:GetAttribute("EquippedWeaponType") or "")
    return RunService:IsStudio() and character:GetAttribute("GameplayTestKind") == "player"
        and (kind == "sword" or kind == "dagger" or kind == "bigsword" or kind == "dualswords")
end
function Fallback.Resolve(character: Model): any?
    if not Fallback.Allowed(character) then return nil end
    local duration = Cadence.DurationForStat(character:GetAttribute("AttackSpeed"))
    local events: any = {HitEnd={time=duration*0.8}}
    if character:GetAttribute("EquippedWeaponType") == "dualswords" then
        events.HitFirst = {time=duration*0.4}
    end
    return {clipId=Fallback.ClipId, duration=duration, playbackDuration=duration,
        playbackSpeed=1, animationSpeedPercent=100, events=events}
end
return table.freeze(Fallback)
