-- Equipment context resolves compatibility, without owning the animation state
-- machine, equip/unequip, attack timing or published asset identity.
local AnimationCompatibility = {}

function AnimationCompatibility.Allowed(row: any, context: string): boolean
    local selected = tostring(context or "unarmed")
    local authored = row.compatibleWith
    if typeof(authored) == "table" then
        -- Empty authored arrays are intentionally valid: disable the clip.
        for _, weaponSet in ipairs(authored) do
            if tostring(weaponSet) == selected then return true end
        end
        return false
    end
    -- Compatibility for pre-M77 profiles (new exports include compatibleWith).
    local kind = tostring(row.weaponSet or "1hs")
    if kind == "base" then
        -- Defaults adapt to future equipment contexts without a second enum.
        return selected ~= "" and selected ~= "base"
    end
    return kind == selected
end

function AnimationCompatibility.Rank(row: any, context: string): number
    -- Prefer authored equipment stance, then reusable base, then other
    -- explicitly compatible clips. Specials are pooled independently.
    if tostring(row.weaponSet) == context then return 1 end
    if tostring(row.weaponSet) == "base" then return 2 end
    return 3
end

return table.freeze(AnimationCompatibility)
