--!strict
-- Server-owned contact schedule; ordinary weapons retain exactly one HitEnd.
local HitEnd = require(script.Parent:WaitForChild("CharacterAttackHitEnd"))
local Plan = {}
function Plan.Resolve(timing: any, dual: boolean, testPreview: boolean): {any}?
    local last = HitEnd.Resolve(timing)
    if not last then return nil end
    if not dual then return {{time=last.time, index=1, count=1}} end
    local first = timing.events and timing.events.HitFirst
    local time = tonumber(first and first.time)
    if not time and testPreview then time = last.time * 0.5 end
    if not time or time ~= time or time < 0 or time >= last.time then return nil end
    return {{time=time,index=1,count=2}, {time=last.time,index=2,count=2}}
end
function Plan.Damage(total: number, index: number, count: number): number
    if count == 1 then return total end
    -- Integer remainder belongs to the second hit (e.g. 141 = 70 + 71).
    local first = math.floor(total / 2)
    return if index == 1 then first else total - first
end
return table.freeze(Plan)
