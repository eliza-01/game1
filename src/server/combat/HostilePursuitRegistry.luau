-- Server-owned index of hostile actors currently targeting a player character.
-- The index is updated on target transitions, never by Workspace scans during attacks.
local HostilePursuitRegistry = {}

type TrackedPursuit = {
    target: Model,
    destroying: RBXScriptConnection,
    lifeStateChanged: RBXScriptConnection,
    targetDestroying: RBXScriptConnection,
    targetLifeStateChanged: RBXScriptConnection,
}

local byHostile: { [Model]: TrackedPursuit } = {}
local pursuerCount: { [Model]: number } = setmetatable({}, { __mode = "k" })

function HostilePursuitRegistry.Clear(hostile: Model)
    local entry = byHostile[hostile]
    if not entry then return end
    byHostile[hostile] = nil
    entry.destroying:Disconnect()
    entry.lifeStateChanged:Disconnect()
    entry.targetDestroying:Disconnect()
    entry.targetLifeStateChanged:Disconnect()
    local remaining = (pursuerCount[entry.target] or 1) - 1
    if remaining > 0 then
        pursuerCount[entry.target] = remaining
    else
        pursuerCount[entry.target] = nil
    end
end

function HostilePursuitRegistry.SetTarget(hostile: Model, target: Model?)
    local existing = byHostile[hostile]
    if existing and existing.target == target then return end
    HostilePursuitRegistry.Clear(hostile)
    if not target or not hostile.Parent or not target.Parent
        or hostile:GetAttribute("LifeState") ~= "Alive" then
        return
    end

    local entry: TrackedPursuit = {
        target = target,
        destroying = hostile.Destroying:Connect(function()
            HostilePursuitRegistry.Clear(hostile)
        end),
        lifeStateChanged = hostile:GetAttributeChangedSignal("LifeState"):Connect(function()
            if hostile:GetAttribute("LifeState") ~= "Alive" then
                HostilePursuitRegistry.Clear(hostile)
            end
        end),
        targetDestroying = target.Destroying:Connect(function()
            HostilePursuitRegistry.Clear(hostile)
        end),
        targetLifeStateChanged = target:GetAttributeChangedSignal("LifeState"):Connect(function()
            if target:GetAttribute("LifeState") ~= "Alive" then
                HostilePursuitRegistry.Clear(hostile)
            end
        end),
    }
    byHostile[hostile] = entry
    pursuerCount[target] = (pursuerCount[target] or 0) + 1
end

function HostilePursuitRegistry.Count(character: Model): number
    return pursuerCount[character] or 0
end

function HostilePursuitRegistry.IsPursued(character: Model): boolean
    return HostilePursuitRegistry.Count(character) > 0
end

return table.freeze(HostilePursuitRegistry)
