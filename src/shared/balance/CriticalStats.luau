--!strict
-- Percentage bonuses scale the equipped chance; flat bonuses are percentage points.
local Balance = require(script.Parent:WaitForChild("Balance"))
local Critical = {}
local function finite(value: any, fallback: number): number
    if type(value) ~= "number" or value ~= value or math.abs(value) == math.huge then return fallback end
    return value
end
function Critical.Chance(base: number, percent: number?, flat: number?): number
    return math.clamp(finite(base, 0) * (1 + finite(percent, 0) / 100) + finite(flat, 0), 0, Balance.Rules.maxCritChance)
end
function Critical.Multiplier(value: any): number
    return math.clamp(finite(value, Balance.Rules.critMultiplier), 1, 5)
end
local function inRange(value: any, minimum: number, maximum: number): boolean
    return type(value) == "number" and value >= minimum and value <= maximum
end
function Critical.ValidateTest(percent: any, flat: any, multiplier: any): (boolean, string?)
    if not inRange(percent, 0, 200) then return false, "Crit buff: 0–200%" end
    if not inRange(flat, 0, 20) then return false, "Crit bonus: 0–20 pp" end
    if not inRange(multiplier, 1, 5) then return false, "Crit damage: 1–5x" end
    return true, nil
end
return table.freeze(Critical)
