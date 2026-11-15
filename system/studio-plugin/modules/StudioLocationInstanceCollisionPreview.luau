-- Instance Manager: disposable collision inspection overlay, never a placed asset.
-- Only clones generated collision primitives from detached, validated staged Models.
local Collision = require(script.Parent.StudioLocationCollisionParts)
local Carrier = require(script.Parent.StudioLocationRigCarrier)
local MeshPhysics = require(script.Parent.StudioMeshPhysicsCore)
local Preview = {}
local MAX_PARTS = 512
-- Keep the temporary overlay attached to the currently active Studio camera.
-- A camera switch must not invalidate an otherwise approved inspection.
local cameraConnections = {}

function Preview.Show(workspaceRef: Workspace, staged: {any}): (Model, number)
    local camera = workspaceRef.CurrentCamera
    if not camera then error("Studio camera unavailable for collision preview") end
    local ghost = Instance.new("Model")
    ghost.Name = "__Game1InstanceCollisionPreview"
    ghost:SetAttribute("Game1AuthoringPreview", true)
    local count = 0
    local visualCount = 0
    local ok, failure = pcall(function()
        for index, pair in ipairs(staged) do
            local warnings = {}
            for _, warning in ipairs(pair.warnings) do warnings[warning.partId] = warning end
            if #pair.warnings > 0 then
                -- Show the proposed target's *visual MeshParts* only for enlarged
                -- colliders, so the author can compare the orange enclosure to
                -- the new mesh. Never clone scripts or authored model behavior.
                for _, object in ipairs(pair.after:GetDescendants()) do
                    if object:IsA("MeshPart") and not Carrier.IsCarrier(object)
                        and not MeshPhysics.IsCollider(object.Name)
                        and object:GetAttribute("Game1DecoPhysicsOnly") ~= true then
                        visualCount += 1
                        if visualCount > MAX_PARTS then
                            error("Too many target visual previews; use Selected scope")
                        end
                        local visual = object:Clone()
                        for _, descendant in ipairs(visual:GetDescendants()) do
                            if descendant:IsA("LuaSourceContainer") then descendant:Destroy() end
                        end
                        visual.Name = "TARGET VISUAL · " .. object.Name
                        visual.CFrame = object.CFrame
                        visual.Anchored = true
                        visual.CanCollide = false
                        visual.CanQuery = false
                        visual.CanTouch = false
                        visual.Transparency = 0.72
                        visual.CastShadow = false
                        visual.Parent = ghost
                    end
                end
            end
            for _, child in ipairs(pair.after:GetChildren()) do
                if Collision.IsOwned(child) then
                    count += 1
                    if count > MAX_PARTS then
                        error("Collision preview exceeds 512 Parts; use Selected scope in smaller batches")
                    end
                    local copy = child:Clone()
                    local issue = warnings[child:GetAttribute("Game1LocationCollisionPartId")]
                    local enlarged = issue ~= nil
                    copy.Name = if issue and issue.approximate then "APPROX · " .. child.Name
                        elseif enlarged then "SHEAR · " .. child.Name else "Collision · " .. child.Name
                    copy:SetAttribute("Game1InspectionPlacementIndex", index)
                    copy:SetAttribute("Game1InspectionExcessive", enlarged)
                    copy.Anchored = true
                    copy.CanCollide = false
                    copy.CanQuery = false
                    copy.CanTouch = false
                    copy.CastShadow = false
                    copy.Material = Enum.Material.Neon
                    copy.Color = if warnings[child:GetAttribute("Game1LocationCollisionPartId")]
                        then Color3.fromRGB(235, 84, 54) else Color3.fromRGB(72, 183, 131)
                    copy.Transparency = if warnings[child:GetAttribute("Game1LocationCollisionPartId")]
                        then 0.45 else 0.72
                    copy.Parent = ghost
                end
            end
        end
        ghost.Parent = camera
    end)
    if not ok then ghost:Destroy(); error(tostring(failure)) end
    cameraConnections[ghost] = workspaceRef:GetPropertyChangedSignal("CurrentCamera"):Connect(function()
        local active = workspaceRef.CurrentCamera
        if ghost.Parent and active then ghost.Parent = active end
    end)
    -- Keep the five-minute leak guard. Disconnect even when Studio destroys
    -- the overlay externally, so no abandoned camera listener remains.
    task.delay(300, function() Preview.Clear(ghost) end)
    return ghost, count
end

function Preview.IsVisible(workspaceRef: Workspace, ghost: Instance?): boolean
    local camera = workspaceRef.CurrentCamera
    if not ghost or not camera or not ghost.Parent then return false end
    if ghost.Parent ~= camera then
        if not ghost.Parent:IsA("Camera") then return false end
        ghost.Parent = camera
    end
    return ghost.Parent == camera
end

-- Locate an already inspected orange collision without changing Studio Selection.
-- This is intentionally camera-only: Selected-scope Replace validates the
-- original selection and a focus command must not invalidate that evidence.
function Preview.Focus(workspaceRef: Workspace, ghost: Instance?, index: number, partId: string): boolean
    if not Preview.IsVisible(workspaceRef,ghost) then return false end
    local match: BasePart? = nil
    for _, child in ipairs(ghost:GetChildren()) do
        if child:IsA("BasePart") and child:GetAttribute("Game1InspectionPlacementIndex") == index
            and child:GetAttribute("Game1LocationCollisionPartId") == partId
            and child:GetAttribute("Game1InspectionExcessive") == true then
            match = child
            break
        end
    end
    if not match then return false end
    local old = ghost:FindFirstChild("__Game1CollisionFocus")
    if old then old:Destroy() end
    local selectionBox = Instance.new("SelectionBox")
    selectionBox.Name = "__Game1CollisionFocus"
    selectionBox.Adornee = match
    selectionBox.LineThickness = 0.08
    selectionBox.Color3 = Color3.fromRGB(255, 180, 60)
    selectionBox.SurfaceTransparency = 1
    selectionBox.Parent = ghost
    local camera = workspaceRef.CurrentCamera
    if not camera then return false end
    local direction = camera.CFrame.LookVector
    local largest = math.max(match.Size.X, match.Size.Y, match.Size.Z)
    local distance = math.clamp(largest * 2.5, 14, 180)
    camera.CFrame = CFrame.lookAt(match.Position - direction * distance,match.Position)
    camera.Focus = CFrame.new(match.Position)
    return true
end

function Preview.Clear(ghost: Instance?)
    if not ghost then return end
    local connection = cameraConnections[ghost]
    if connection then
        connection:Disconnect()
        cameraConnections[ghost] = nil
    end
    ghost:Destroy()
end

return table.freeze(Preview)
