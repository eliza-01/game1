--!strict
local Workspace = game:GetService("Workspace")
local Physics = require(game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
    :WaitForChild("world"):WaitForChild("MeshPhysicsCore"))
local Raycast = {}
local visuals: {[BasePart]: MeshPart} = setmetatable({}, {__mode = "kv"}) :: any
function Raycast.Bind(proxy: BasePart, mesh: MeshPart)
    visuals[proxy] = mesh
end
function Raycast.Unbind(proxy: BasePart, mesh: MeshPart)
    if visuals[proxy] == mesh then visuals[proxy] = nil end
end
function Raycast.DoorOf(socket: Attachment): Model?
    local node: Instance? = socket.Parent
    while node and node ~= Workspace do
        if node:IsA("Model") then
            if node.Name == "DoorAssembly" then return node end
            local door = node:FindFirstChild("DoorAssembly")
            if door and door:IsA("Model") then return door end
        end
        node = node.Parent
    end
    return nil
end
-- Called only with nearby eligible doors. Query the actual visual meshes, not
-- the invisible runtime boxes. Restore local query flags before returning;
-- no yields and no changes to normal combat/physics query policy.
function Raycast.Hit(origin: Vector3, direction: Vector3, distance: number,
    doors: {[Model]: boolean}, character: Model?): (Model?, number)
    if next(doors) == nil or distance <= 0 then return nil, math.huge end
    local owners: {[BasePart]: Model} = {}
    local excluded: {Instance} = if character then {character} else {}
    local changed: {BasePart} = {}
    for door in doors do
        for _, part in door:GetDescendants() do
            if not part:IsA("BasePart") then continue end
            local visual = visuals[part]
            local mesh = if visual and visual:IsDescendantOf(Workspace) then visual
                else if part:IsA("MeshPart") and part.Transparency < 1
                    and not Physics.IsLocationCarrier(part) and not Physics.IsCollider(part.Name)
                    and part:GetAttribute("Game1DecoPhysicsOnly") ~= true then part else nil
            if mesh then
                owners[mesh] = door
                if mesh ~= part then table.insert(excluded, part) end
                if not mesh.CanQuery then
                    mesh.CanQuery = true
                    table.insert(changed, mesh)
                end
            else
                -- Door carriers and invisible proxies cannot stand in for a mesh.
                table.insert(excluded, part)
            end
        end
    end
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = excluded
    params.IgnoreWater = true
    local ok, hit = pcall(function() return Workspace:Raycast(origin, direction * distance, params) end)
    for _, part in changed do part.CanQuery = false end
    if ok and hit then return owners[hit.Instance], hit.Distance end
    return nil, math.huge
end
return table.freeze(Raycast)
