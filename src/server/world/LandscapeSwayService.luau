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

-- M358: server sector contact without weapon volume or client box transforms.
-- Sway proxies are immutable authoring output and queried with a bounded radius.
function Service.MeleeArc(root: BasePart, reach: number, arcAngle: number, facingDirection: Vector3?)
    if not remote or not root or not root.Parent then return end
    local decor = Workspace:FindFirstChild(ROOT)
    if not decor then return end
    local params = OverlapParams.new()
    params.FilterType = Enum.RaycastFilterType.Include
    params.FilterDescendantsInstances = {decor}
    params.MaxParts = 24
    local chosen = facingDirection or root.CFrame.LookVector
    local forward = Vector3.new(chosen.X, 0, chosen.Z)
    if forward.Magnitude <= 1e-6 then return end
    local threshold = math.cos(math.rad(math.clamp(arcAngle, 1, 360)) * 0.5)
    for _, part in ipairs(Workspace:GetPartBoundsInRadius(root.Position, reach, params)) do
        if part.Name == "LandscapeSwayTarget" and part:GetAttribute("Game1LandscapeSwayTarget") == true then
            local delta = part.Position - root.Position
            local horizontal = Vector3.new(delta.X, 0, delta.Z)
            if horizontal.Magnitude < 0.01 or arcAngle >= 360
                or horizontal.Unit:Dot(forward.Unit) >= threshold then
                Service.Impact(part, part.Position, if delta.Magnitude > 0.01 then delta else forward)
            end
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
