--!strict
-- Locally evaluated Bone.Transform: Roblox does not replicate this property.
-- Server owns the Game1WindmillDoorOpen transition; client only interpolates.
local Workspace = game:GetService("Workspace")
local Door = {}
local OPEN_ANGLE = math.rad(90)
local DURATION = 0.55

export type State = {hinge: Bone}

function Door.Bind(model: Model): State?
    local hinge: Bone? = nil
    for _, child in model:GetDescendants() do
        if child.Name == "windmill_door_socket" and child:IsA("Bone") then
            if hinge then return nil end
            hinge = child
        end
    end
    if not hinge then return nil end
    return {hinge = hinge}
end

function Door.Update(model: Model, state: State, now: number)
    if not state.hinge.Parent then return end
    local open = model:GetAttribute("Game1WindmillDoorOpen") == true
    local changed = model:GetAttribute("Game1WindmillDoorChangedAt")
    local fraction = 1
    if typeof(changed) == "number" then
        fraction = math.clamp((now - changed) / DURATION, 0, 1)
        fraction = fraction * fraction * (3 - 2 * fraction)
    end
    local degrees = if open then fraction else 1 - fraction
    state.hinge.Transform = CFrame.Angles(0, OPEN_ANGLE * degrees, 0)
end

function Door.Reset(state: State)
    if state.hinge.Parent then state.hinge.Transform = CFrame.identity end
end

return table.freeze(Door)
