-- Compose independent local visibility reasons (LOD and NPC weapon policy).
-- Never modify replicated Transparency/physics or overwrite another owner.
local Visibility = {}
local states = setmetatable({}, {__mode = "k"})
function Visibility.Set(part, owner, hidden)
    local state = states[part]
    if hidden then
        if not state then
            state = {original = part.LocalTransparencyModifier, owners = {}}
            states[part] = state
        end
        state.owners[owner] = true
        part.LocalTransparencyModifier = 1
    elseif state then
        state.owners[owner] = nil
        if next(state.owners) == nil then
            part.LocalTransparencyModifier = state.original
            states[part] = nil
        end
    end
end
function Visibility.Full(model)
    local stage = model:GetAttribute("Game1MnpcLocalLod")
    return stage == nil or stage == "FULL"
end
return table.freeze(Visibility)
