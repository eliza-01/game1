-- Studio-only, non-destructive distance probe for tagged Location Asset Models.
-- This module never changes the geometry or source model.
local RunService = game:GetService("RunService")
local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Players = game:GetService("Players")
local Workspace = game:GetService("Workspace")

local TAG = "Game1LocationLodProbe"
local INTERVAL = 0.25
local LIMIT = 32
local Probe = {}
local started = false

local function makeStatus(player)
    local screen = Instance.new("ScreenGui")
    screen.Name = "Game1LodProbeStatus"
    screen.ResetOnSpawn = false
    screen.DisplayOrder = 110
    local label = Instance.new("TextLabel")
    label.Name = "Status"
    label.Size = UDim2.fromOffset(390, 46)
    label.Position = UDim2.fromOffset(12, 90)
    label.BackgroundTransparency = 0.22
    label.BackgroundColor3 = Color3.fromRGB(17, 23, 31)
    label.TextColor3 = Color3.fromRGB(230, 243, 255)
    label.TextSize = 14
    label.TextWrapped = true
    label.TextXAlignment = Enum.TextXAlignment.Left
    label.Text = "LOD Probe | starting..."
    label.Parent = screen
    screen.Parent = player:WaitForChild("PlayerGui")
    return label
end

function Probe.Start()
    if started or not RunService:IsStudio() then return end
    started = true
    local player = Players.LocalPlayer
    if not player then
        warn("[game1][LOD probe] LocalPlayer missing")
        return
    end
    local status = makeStatus(player)
    local shared = ReplicatedStorage:WaitForChild("Game1Shared", 10)
    local world = shared and shared:WaitForChild("world", 10)
    local policyModule = world and world:WaitForChild("LocationLodDistancePolicy", 10)
    if not policyModule then
        status.Text = "LOD Probe | policy missing (check Rojo)"
        warn("[game1][LOD probe] Shared policy missing in ReplicatedStorage.Game1Shared.world")
        return
    end
    local Policy = require(policyModule)
    local monitored = {}
    local count = 0

    local function findAdornee(model)
        local primary = model.PrimaryPart
        if primary and primary:IsDescendantOf(model) then
            return primary
        end
        return model:FindFirstChildWhichIsA("BasePart", true)
    end

    -- A tagged Model may replicate before its MeshParts (StreamingEnabled).
    -- Keep it pending until its geometry arrives; never give up after one lookup.
    local function refreshGeometry(model, record)
        local previous = record.adorn
        if previous and previous:IsDescendantOf(model) then
            return true
        end
        local current = findAdornee(model)
        record.adorn = current
        record.gui.Adornee = current
        if current then
            print("[game1][LOD probe] Geometry ready: " .. model:GetFullName())
        elseif previous then
            print("[game1][LOD probe] Geometry streamed out: " .. model:GetFullName())
        end
        return current ~= nil
    end

    local function stop(model)
        local record = monitored[model]
        if not record then return end
        monitored[model] = nil
        count -= 1
        if record.gui then record.gui:Destroy() end
    end

    local function add(model)
        if monitored[model] or not model:IsA("Model") or count >= LIMIT then return end
        if not model:IsDescendantOf(Workspace) then return end
        local gui = Instance.new("BillboardGui")
        gui.Name = "Game1LodStudioProbe"
        -- Adornee is assigned when a BasePart actually reaches this client.
        gui.Size = UDim2.fromOffset(210, 40)
        gui.StudsOffsetWorldSpace = Vector3.new(0, 3, 0)
        gui.AlwaysOnTop = true
        local label = Instance.new("TextLabel")
        label.BackgroundTransparency = 0.3
        label.BackgroundColor3 = Color3.fromRGB(18, 18, 18)
        label.TextColor3 = Color3.new(1, 1, 1)
        label.TextSize = 14
        label.Size = UDim2.fromScale(1, 1)
        label.Parent = gui
        gui.Parent = player:WaitForChild("PlayerGui")
        local record = {gui = gui, label = label, state = nil, adorn = nil}
        monitored[model] = record
        count += 1
        if refreshGeometry(model, record) then
            print("[game1][LOD probe] Tracking: " .. model:GetFullName())
        else
            print("[game1][LOD probe] Pending streamed geometry: " .. model:GetFullName())
        end
    end

    CollectionService:GetInstanceAddedSignal(TAG):Connect(add)
    CollectionService:GetInstanceRemovedSignal(TAG):Connect(stop)
    for _, model in ipairs(CollectionService:GetTagged(TAG)) do add(model) end
    print(("[game1][LOD probe] Ready | %d tagged Model(s) | IsStudio=true")
        :format(count))

    task.spawn(function()
        while true do
            task.wait(INTERVAL)
            local camera = Workspace.CurrentCamera
            local nearestDistance = math.huge
            local nearestState = nil
            local ready = 0
            for model, record in pairs(monitored) do
                if not model:IsDescendantOf(Workspace) then
                    stop(model)
                elseif refreshGeometry(model, record) then
                    ready += 1
                    if camera then
                        local distance = (camera.CFrame.Position - model:GetPivot().Position).Magnitude
                        local nextState = Policy.Resolve(distance, record.state)
                        if record.state ~= nextState then
                            print(("[game1][LOD probe] %s: %s -> %s (%.1f studs)")
                                :format(model:GetFullName(), record.state or "INITIAL", nextState, distance))
                            record.state = nextState
                        end
                        record.label.Text = ("LOD policy: %s | %.0f studs"):format(nextState, distance)
                        if distance < nearestDistance then
                            nearestDistance = distance
                            nearestState = nextState
                        end
                    end
                end
            end
            if count == 0 then
                status.Text = "LOD Probe | ACTIVE | 0 tagged Models in Workspace\nCheck tag or client streaming"
            elseif ready == 0 then
                status.Text = ("LOD Probe | ACTIVE | %d tagged | 0 with geometry\nWaiting for streamed BaseParts"):format(count)
            elseif not camera then
                status.Text = ("LOD Probe | ACTIVE | %d tagged | %d ready\nWaiting for camera"):format(count, ready)
            else
                status.Text = ("LOD Probe | ACTIVE | %d tagged | %d ready\nNearest: %.0f studs / %s")
                    :format(count, ready, nearestDistance, nearestState or "—")
            end
        end
    end)
end

return Probe
