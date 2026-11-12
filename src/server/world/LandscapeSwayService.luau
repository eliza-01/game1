-- Server-authoritative impact notifications and a future weather event entrypoint.
-- No moving assemblies, physics simulation or ongoing Workspace polling.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Service = {}
local started = false
local remote: RemoteEvent? = nil
local recent: {[Model]: number} = setmetatable({}, {__mode = "k"})
local RADIUS = 160
local ROOT = "Game1LandscapeDecor"

local function targetFor(part: Instance?): Model?
    local current = part
    while current and current ~= Workspace do
        if current:IsA("Model") and current:GetAttribute("LandscapeAuthoringTool") == "Game1LandscapePainter"
            and current:GetAttribute("LandscapeSwayEnabled") == true
            and current:GetAttribute("LandscapeTetherEnabled") == true then
            return current
        end
        current = current.Parent
    end
    return nil
end

function Service.Impact(part: Instance?, contact: Vector3, direction: Vector3)
    local model = targetFor(part)
    if not model or typeof(contact) ~= "Vector3" or typeof(direction) ~= "Vector3" or direction.Magnitude < 0.01 then return end
    local now = os.clock()
    if now - (recent[model] or -100) < 0.18 then return end
    recent[model] = now
    if not remote then return end
    for _, player in ipairs(Players:GetPlayers()) do
        local character = player.Character
        local root = character and (character:FindFirstChild("RootCollider")
            or character:FindFirstChild("HumanoidRootPart")
            or character:FindFirstChild("NavigationRoot"))
        if root and root:IsA("BasePart") and (root.Position - contact).Magnitude <= RADIUS then
            remote:FireClient(player, "impact", model, direction.Unit)
        end
    end
end

-- Bounded melee target query. Queryable proxy is authored exactly once per sway model.
function Service.Melee(volume: any, attackerPosition: Vector3)
    if not remote or typeof(attackerPosition) ~= "Vector3" then return end
    local decor = Workspace:FindFirstChild(ROOT)
    if not decor or typeof(volume) ~= "table" or typeof(volume.cframe) ~= "CFrame"
        or typeof(volume.size) ~= "Vector3" then return end
    local params = OverlapParams.new()
    params.FilterType = Enum.RaycastFilterType.Include
    params.FilterDescendantsInstances = {decor}
    params.MaxParts = 24
    for _, part in ipairs(Workspace:GetPartBoundsInBox(volume.cframe, volume.size, params)) do
        if part.Name == "LandscapeSwayTarget" and part:GetAttribute("Game1LandscapeSwayTarget") == true then
            local direction = part.Position - attackerPosition
            Service.Impact(part, part.Position, if direction.Magnitude > 0.01 then direction else volume.cframe.LookVector)
        end
    end
end

-- Weather system integration: call LandscapeSwayService.Wind(strength, seconds).
-- Sound is played locally only when a real published asset ID is configured.
function Service.Wind(strength: number, seconds: number)
    if not remote then return end
    if type(strength) ~= "number" or strength ~= strength or type(seconds) ~= "number" or seconds ~= seconds then return end
    remote:FireAllClients("wind", math.clamp(strength, 0, 1), math.clamp(seconds, 0, 30))
end

function Service.Start()
    if started then return end
    started = true
    local folder = ReplicatedStorage:FindFirstChild("Game1Remotes")
    if not folder then folder = Instance.new("Folder"); folder.Name = "Game1Remotes"; folder.Parent = ReplicatedStorage end
    local existing = folder:FindFirstChild("LandscapeSwayEvent")
    if existing and not existing:IsA("RemoteEvent") then error("LandscapeSwayEvent must be RemoteEvent") end
    remote = existing or Instance.new("RemoteEvent")
    remote.Name = "LandscapeSwayEvent"
    remote.Parent = folder
end

return table.freeze(Service)
