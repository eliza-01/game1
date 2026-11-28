-- Attach-time Character component definitions; no cloud reads or frame work.
local Definitions = require(script.Parent:WaitForChild("HitboxAssetDefinitions"))
local Builder = require(script.Parent:WaitForChild("HitboxDefinitionBuilder"))
local Components = {}
local warned, accepted = {}, {}
local function key(single)
    return "component|" .. Builder.AssetKey(single)
end

function Components.Lookup(binding)
    local archetype = binding.entity:GetAttribute("CharacterArchetype")
    if not archetype then return nil end
    local definitions = {}
    for index = 1, #binding.records do
        local single = Definitions.ComponentBinding(binding, index)
        local componentKey = key(single)
        local definition, reason = Definitions.LookupComponent(single, componentKey)
        if not definition then
            if not warned[componentKey] then
                warned[componentKey] = true
                warn("[game1][hitbox-components] " .. tostring(reason) .. ": " .. single.records[1].path)
            end
            return nil -- atomic all-or-nothing; no mixed oracle/asset head union
        end
        table.insert(definitions, definition)
    end
    local merged = Builder.MergeComponents(binding, definitions)
    local assemblyKey = Builder.AssetKey(binding)
    if not accepted[assemblyKey] then
        accepted[assemblyKey] = true
        print(("[game1][hitbox-components] accepted %s · %d components · %d boxes"):format(archetype, #definitions,
            #merged.bodyBoxes + (if merged.headBox then 1 else 0)))
    end
    return merged
end

local function compareBox(a,b)
    assert(a.kind == b.kind and a.recordIndex == b.recordIndex and a.boneName == b.boneName
        and (a.localCFrame.Position - b.localCFrame.Position).Magnitude <= 0.00001
        and (a.size - b.size).Magnitude <= 0.00001, "component oracle box mismatch")
end

function Components.Capture(binding, oracle)
    assert(Definitions.Signature(binding), "unpublished or ambiguous character assembly")
    local rows, definitions = {}, {}
    for index, record in ipairs(binding.records) do
        local single = Definitions.ComponentBinding(binding, index)
        local definition, reason, rawHead = Builder.BuildUncached(single)
        assert(definition, reason or "component oracle failed")
        definition.rawHead = rawHead
        table.insert(definitions, definition)
        table.insert(rows, Definitions.AuthoringRow(single, key(single), definition,
            Definitions.ComponentDependencies(record), rawHead))
    end
    local merged = Builder.MergeComponents(binding, definitions)
    assert(#merged.bodyBoxes == #oracle.bodyBoxes and merged.sourceVertexCount == oracle.sourceVertexCount
        and math.abs(merged.broadRadius - oracle.broadRadius) <= 0.00001
        and (merged.headBox ~= nil) == (oracle.headBox ~= nil), "component oracle metadata mismatch")
    for i, box in ipairs(merged.bodyBoxes) do compareBox(box, oracle.bodyBoxes[i]) end
    if merged.headBox then compareBox(merged.headBox, oracle.headBox) end
    return rows
end

return table.freeze(Components)
