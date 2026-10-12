-- NPC-only Studio placement gesture. Monster placement remains unchanged.
-- Hover to select the ground, press LMB to lock the point, drag horizontally
-- to rotate the published rig, release LMB to commit; Escape cancels.
local NpcSpawnPlacement = {}

local ROTATION_DEGREES_PER_PIXEL = 0.65
local TIMEOUT_SECONDS = 295

local function positionFromData(value: any): Vector3?
    if type(value) ~= "table" then
        return nil
    end
    local x, y, z = tonumber(value.x), tonumber(value.y), tonumber(value.z)
    if not x or not y or not z then
        return nil
    end
    return Vector3.new(x, y, z)
end

function NpcSpawnPlacement.Place(context: any): any
    local plugin = context.plugin
    local workspace = context.Workspace
    local userInput = context.UserInputService
    local mouse = plugin:GetMouse()
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.RespectCanCollide = true
    local excluded: {Instance} = {}
    local authoring = workspace:FindFirstChild("Game1Authoring")
    if authoring then
        table.insert(excluded, authoring)
    end
    local npcs = workspace:FindFirstChild("NPCs")
    if npcs then
        table.insert(excluded, npcs)
    end
    params.FilterDescendantsInstances = excluded

    local function groundHit(): RaycastResult?
        local ray = mouse.UnitRay
        return workspace:Raycast(ray.Origin, ray.Direction * 10000, params)
    end

    local connections: {RBXScriptConnection} = {}
    local marker: Model? = nil
    local finished = false
    local cancelled = false
    local dragging = false
    local initialX = 0
    local initialYaw = 0
    local yaw = (tonumber(context.data.yawDegrees) or context.cameraYaw()) % 360
    local selected = positionFromData(context.data.position) or Vector3.zero
    local hasGround = false
    local targetName = ""
    local deadline = os.clock() + TIMEOUT_SECONDS

    local ok, result = xpcall(function()
        plugin:Activate(true)
        local firstHit = groundHit()
        if firstHit then
            selected = firstHit.Position
            hasGround = true
        end
        context.data.position = {x = selected.X, y = selected.Y, z = selected.Z}
        context.data.yawDegrees = yaw
        context.data.placeId = game.PlaceId
        marker = context.createMarker(context.data, "preview", "npc")

        local function redraw()
            if marker then
                context.moveMarker(marker, selected, yaw)
            end
        end
        redraw()
        table.insert(connections, mouse.Move:Connect(function()
            if dragging then
                yaw = (initialYaw + (mouse.X - initialX) * ROTATION_DEGREES_PER_PIXEL) % 360
                redraw()
            else
                local hit = groundHit()
                if hit then
                    selected = hit.Position
                    hasGround = true
                    redraw()
                else
                    hasGround = false
                end
            end
        end))
        table.insert(connections, mouse.Button1Down:Connect(function()
            if dragging then
                return
            end
            local hit = groundHit()
            if not hit then
                return
            end
            selected = hit.Position
            targetName = hit.Instance:GetFullName()
            hasGround = true
            initialX = mouse.X
            initialYaw = yaw
            dragging = true
            redraw()
        end))
        local function release()
            if dragging then
                dragging = false
                finished = true
            end
        end
        table.insert(connections, mouse.Button1Up:Connect(release))
        -- Also handle releasing outside the viewport while Studio owns capture.
        table.insert(connections, userInput.InputEnded:Connect(function(input)
            if input.UserInputType == Enum.UserInputType.MouseButton1 then
                release()
            end
        end))
        table.insert(connections, userInput.InputBegan:Connect(function(input)
            if input.KeyCode == Enum.KeyCode.Escape then
                cancelled = true
            end
        end))
        table.insert(connections, plugin.Deactivation:Connect(function()
            cancelled = true
        end))

        repeat
            task.wait(0.05)
        until finished or cancelled or os.clock() >= deadline
        if not finished or cancelled then
            error(cancelled and "NPC Spawn placement cancelled" or "NPC Spawn placement timed out")
        end
        return {
            position = {x = selected.X, y = selected.Y, z = selected.Z},
            yawDegrees = yaw,
            target = targetName,
            markerPath = (marker :: Model):GetFullName(),
        }
    end, debug.traceback)

    for _, connection in ipairs(connections) do
        connection:Disconnect()
    end
    plugin:Deactivate()
    if not ok then
        if marker then
            marker:Destroy()
        end
        error(result)
    end
    return result
end

return table.freeze(NpcSpawnPlacement)
