--!strict
-- Client visual only: rigid blades and fabric share ONE pivot and ONE phase.
-- Never write publication MeshId/PivotOffset, Bones, or model ancestry.
local Rotor = {}

export type State = {
    blades: MeshPart,
    fabric: MeshPart,
    bladesCFrame: CFrame,
    fabricCFrame: CFrame,
    pivot: CFrame,
}

local function uniqueMesh(model: Model, name: string): MeshPart?
    local found: MeshPart? = nil
    for _, child in model:GetDescendants() do
        if child.Name == name and child:IsA("MeshPart") then
            if found then return nil end -- ambiguous publication: fail closed
            found = child
        end
    end
    return found
end

function Rotor.Bind(model: Model): State?
    local blades = uniqueMesh(model, "blades")
    local fabric = uniqueMesh(model, "fabric")
    if not blades or not fabric then return nil end
    -- fabric's mesh bounds are centered on the rotor axle in windmill_02.
    -- Use its authored CFrame as the SHARED rotation frame. The MeshPart
    -- GetPivot() can be the FBX scene origin rather than the axle center.
    return {
        blades = blades,
        fabric = fabric,
        bladesCFrame = blades.CFrame,
        fabricCFrame = fabric.CFrame,
        pivot = fabric.CFrame,
    }
end

function Rotor.Update(state: State, seconds: number, secondsPerRevolution: number)
    if not state.blades.Parent or not state.fabric.Parent then return end
    local phase = (seconds % secondsPerRevolution) / secondsPerRevolution
    local rotation = state.pivot * CFrame.Angles(0, 0, phase * math.pi * 2) * state.pivot:Inverse()
    state.blades.CFrame = rotation * state.bladesCFrame
    state.fabric.CFrame = rotation * state.fabricCFrame
end

function Rotor.Reset(state: State)
    if state.blades.Parent then state.blades.CFrame = state.bladesCFrame end
    if state.fabric.Parent then state.fabric.CFrame = state.fabricCFrame end
end

return table.freeze(Rotor)
