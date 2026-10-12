-- Data-driven weighted choice shared by actor presentation systems.
-- Zero weight means disabled; negative/non-finite values are ignored.
-- The caller owns timing and selection eligibility (combat, locomotion, death).
local WeightedAnimationChoice = {}

function WeightedAnimationChoice.Select(choices: {any}, random: Random): any?
    local total = 0
    for _, choice in ipairs(choices) do
        local weight = tonumber(choice.row and choice.row.weight)
        if weight and weight == weight and weight < math.huge and weight > 0 then
            total += weight
        end
    end
    if total <= 0 then
        return nil
    end
    local roll = random:NextNumber(0, total)
    local cumulative = 0
    for _, choice in ipairs(choices) do
        local weight = tonumber(choice.row and choice.row.weight)
        if weight and weight == weight and weight < math.huge and weight > 0 then
            cumulative += weight
            if roll < cumulative then
                return choice
            end
        end
    end
    -- Defend against floating-point rounding at the upper bound.
    for index = #choices, 1, -1 do
        local choice = choices[index]
        local weight = tonumber(choice.row and choice.row.weight)
        if weight and weight == weight and weight < math.huge and weight > 0 then
            return choice
        end
    end
    return nil
end

return table.freeze(WeightedAnimationChoice)
