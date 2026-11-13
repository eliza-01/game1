-- Pure combat-feedback policy. Does not authorize damage or select hit targets.
local AttackFeedbackPolicy = {}

AttackFeedbackPolicy.MeleeFarCooldownSeconds = 10

-- Called only after the server confirms that an attack dealt no damage.
-- Melee Miss requires one actual target under the validated reticle ray.
-- Swept weapon volume can damage many monsters, but never yields per-target
-- Miss notifications. Bow retains its pursuit-based miss rule from M323.
function AttackFeedbackPolicy.Resolve(pursued: boolean, aimedState: string?, isBow: boolean): string?
    if aimedState == "out_of_range_monster" then
        return "far"
    end
    if aimedState == "in_range" or (isBow and pursued) then
        return "miss"
    end
    return nil
end

-- During the player's own melee animation, suppress incoming enemy Miss
-- labels: otherwise three pursuing monsters can spam Miss above a player who
-- is visibly dealing damage. Incoming feedback still works outside that window.
function AttackFeedbackPolicy.AllowIncomingMiss(attackEndsAt: any, weaponType: any, now: number): boolean
    local endsAt = tonumber(attackEndsAt)
    return not (endsAt and endsAt > now
        and string.lower(tostring(weaponType or "")) ~= "bow")
end

function AttackFeedbackPolicy.CanShowMeleeFar(lastShownAt: number?, now: number): boolean
    return lastShownAt == nil or now - lastShownAt >= AttackFeedbackPolicy.MeleeFarCooldownSeconds
end

return table.freeze(AttackFeedbackPolicy)
