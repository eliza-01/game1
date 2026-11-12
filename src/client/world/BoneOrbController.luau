-- Cosmetic levitating Bone orbs. Fire Tuner authors a tagged Attachment directly
-- under ANY Bone; no bone name, server physics, damage, or heartbeat per orb.
local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Controller = {}
local TAG = "Game1LightOrb"
local RADIUS = 140
local MAX_ACTIVE = 32
local TICK = 1 / 30
local RESCAN = 1.25
local active = {}
local started = false
local folder

local function rootPosition(): Vector3?
    local player = Players.LocalPlayer
    local character = player and player.Character
    if not character then return nil end
    local root = character:FindFirstChild("RootCollider")
        or character:FindFirstChild("HumanoidRootPart")
        or character:FindFirstChild("NavigationRoot")
    return if root and root:IsA("BasePart") then root.Position else nil
end

local function orbPart(): BasePart
    if not folder or not folder.Parent then
        folder = Instance.new("Folder")
        folder.Name = "Game1LocalBoneOrbs"
        folder.Parent = Workspace
    end
    local part = Instance.new("Part")
    part.Name = "BoneOrb"
    part.Shape = Enum.PartType.Ball
    part.Material = Enum.Material.Neon
    part.Anchored = true
    part.CanCollide = false
    part.CanTouch = false
    part.CanQuery = false
    part.CastShadow = false
    local light = Instance.new("PointLight")
    light.Name = "OrbLight"
    light.Parent = part
    part.Parent = folder
    return part
end

local function remove(attachment: Attachment)
    local state = active[attachment]
    if state then
        if state.part then state.part:Destroy() end
        active[attachment] = nil
    end
end

local function rescan()
    local origin = rootPosition()
    if not origin then
        for attachment in pairs(active) do remove(attachment) end
        return
    end
    local candidates = {}
    for _, item in ipairs(CollectionService:GetTagged(TAG)) do
        if item.ClassName == "Attachment" and item.Parent and item.Parent:IsA("Bone")
            and item:IsDescendantOf(Workspace) and item:GetAttribute("Enabled") == true then
            local distance = (item.WorldPosition - origin).Magnitude
            if distance < RADIUS then
                table.insert(candidates, {attachment = item, distance = distance})
            end
        end
    end
    table.sort(candidates, function(a, b) return a.distance < b.distance end)
    local keep = {}
    for i = 1, math.min(MAX_ACTIVE, #candidates) do
        local attachment = candidates[i].attachment
        keep[attachment] = true
        if not active[attachment] then
            active[attachment] = {part = orbPart(), phase = i * 1.17,
                wanderSeed = math.random(1, 100000)}
        end
    end
    for attachment in pairs(active) do
        if not keep[attachment] then remove(attachment) end
    end
end

local function animate()
    for attachment, state in pairs(active) do
        if not attachment.Parent or attachment.Parent.ClassName ~= "Bone"
            or attachment:GetAttribute("Enabled") ~= true then
            remove(attachment)
        else
            local bone = attachment.Parent :: Bone
            local frame = bone.TransformedWorldCFrame * attachment.CFrame
            local t = os.clock() * math.pi * 2
                * math.clamp(tonumber(attachment:GetAttribute("BobFrequency")) or 0.35, 0, 3)
                + state.phase
            local pos = frame.Position + Vector3.yAxis * (
                math.clamp(tonumber(attachment:GetAttribute("Lift")) or 0.4, -3, 6)
                + math.sin(t) * math.clamp(tonumber(attachment:GetAttribute("BobAmplitude")) or 0.12, 0, 2))
                + frame.RightVector * math.sin(t * 0.73) *
                    math.clamp(tonumber(attachment:GetAttribute("Drift")) or 0.08, 0, 2)
            -- Smooth, non-physics wandering inside the authored roam radius.
            -- Noise avoids per-frame random impulses and never drifts unboundedly.
            local roamRadius = math.clamp(tonumber(attachment:GetAttribute("RoamRadius")) or 0, 0, 10)
            if roamRadius > 0 then
                local speed = math.clamp(tonumber(attachment:GetAttribute("RoamSpeed")) or 0.5, 0.05, 3)
                local sampleTime = os.clock() * speed * 0.4
                local seed = state.wanderSeed
                local wander = Vector3.new(
                    math.noise(seed, sampleTime, 0),
                    math.noise(seed, sampleTime, 17),
                    math.noise(seed, sampleTime, 37)
                )
                pos += wander * roamRadius
            end
            local part = state.part
            local radius = math.clamp(tonumber(attachment:GetAttribute("Radius")) or 0.22, 0.06, 1.5)
            part.Size = Vector3.new(radius * 2, radius * 2, radius * 2)
            part.Position = pos
            local color = attachment:GetAttribute("Color")
            part.Color = if typeof(color) == "Color3" then color else Color3.fromRGB(255, 224, 145)
            local light = part:FindFirstChildOfClass("PointLight")
            light.Color = part.Color
            light.Brightness = math.clamp(tonumber(attachment:GetAttribute("Brightness")) or 1.65, 0, 8)
            light.Range = math.clamp(tonumber(attachment:GetAttribute("Range")) or 33.5, 0, 60)
            light.Shadows = attachment:GetAttribute("Shadows") == true
        end
    end
end

function Controller.Start()
    if started then return end
    started = true
    local acc, scan = 0, RESCAN
    RunService.Heartbeat:Connect(function(dt)
        acc += dt
        scan += dt
        if scan >= RESCAN then scan = 0; rescan() end
        if acc >= TICK then acc %= TICK; animate() end
    end)
end

return table.freeze(Controller)
