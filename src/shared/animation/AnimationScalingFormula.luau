-- Pure, actor-agnostic arithmetic for authored animation speed scaling.
-- Intentionally independent of Roblox services, registries and Instance attributes.
local Formula = {}

Formula.MinPercent = 1
Formula.MaxPercent = 400
Formula.MinUnitsPerPercent = 0.001
Formula.MaxUnitsPerPercent = 1000

function Formula.Finite(value, fallback)
    local numeric = tonumber(value)
    if numeric == nil or numeric ~= numeric or numeric == math.huge or numeric == -math.huge then
        return fallback
    end
    return numeric
end

function Formula.StatValue(value)
    return math.max(0, Formula.Finite(value, 0))
end

function Formula.AuthoredUnits(units)
    return math.clamp(
        Formula.Finite(units, 1),
        Formula.MinUnitsPerPercent,
        Formula.MaxUnitsPerPercent
    )
end

function Formula.DebugUnits(units, authoredUnits)
    return math.clamp(
        Formula.Finite(units, authoredUnits),
        Formula.MinUnitsPerPercent,
        Formula.MaxUnitsPerPercent
    )
end

function Formula.DetailsPercent(statValue, unitsPerPercent)
    local value = Formula.StatValue(statValue)
    return math.clamp(value / unitsPerPercent, Formula.MinPercent, Formula.MaxPercent)
end

-- Preserve the historical bare-rule API separately from details resolution:
-- it enforces a minimum divisor but not an upper bound on authored units.
function Formula.RulePercent(statValue, ruleUnits)
    local unitsPerPercent = math.max(0.001, Formula.Finite(ruleUnits, 1))
    return Formula.DetailsPercent(statValue, unitsPerPercent)
end

return table.freeze(Formula)
