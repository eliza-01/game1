-- Studio-only melee sector preview. Beam endpoints are local attachments under
-- RootCollider, so the entire sector follows the character without per-frame
-- rebuilding or moving 69 anchored Parts. This does NOT perform hit queries.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local MeleeArcPreview = {}
MeleeArcPreview.__index = MeleeArcPreview

local SEGMENTS = 64
local ACCENT = Color3.fromRGB(72, 214, 180)

local function attachment(root: BasePart, position: Vector3): Attachment
    local item = Instance.new("Attachment")
    item.Name = "MeleeArcDebugAnchor"
    item.Position = position
    item.Visible = false
    item.Parent = root
    return item
end

local function beam(folder: Folder, name: string, first: Attachment, last: Attachment,
    width: number, opacity: number): Beam
    local item = Instance.new("Beam")
    item.Name = name
    item.Attachment0 = first
    item.Attachment1 = last
    item.Width0 = width
    item.Width1 = width
    item.Segments = 1
    item.FaceCamera = true
    item.LightEmission = 0.6
    item.Transparency = NumberSequence.new(opacity)
    item.Color = ColorSequence.new(ACCENT)
    item.Parent = folder
    return item
end

function MeleeArcPreview.new(): any
    local folder = Instance.new("Folder")
    folder.Name = "Game1AttackRadiusPreview"
    local ray = Instance.new("Part")
    ray.Name = "HeadshotAimRay"
    ray.Anchored = true
    ray.CanCollide = false
    ray.CanQuery = false
    ray.CanTouch = false
    ray.CastShadow = false
    ray.Material = Enum.Material.SmoothPlastic
    ray.Color = Color3.fromRGB(255, 205, 108)
    ray.Transparency = 1
    ray.Parent = folder

    return setmetatable({
        _folder = folder,
        _aimRay = ray,
        _root = nil,
        _anchors = {},
        _beams = {},
        _radius = nil,
        _arc = nil,
        _height = nil,
        _connection = nil,
        _visible = false,
    }, MeleeArcPreview)
end

function MeleeArcPreview:_clearGeometry()
    for _, item in ipairs(self._beams) do item:Destroy() end
    for _, item in ipairs(self._anchors) do item:Destroy() end
    table.clear(self._beams)
    table.clear(self._anchors)
    self._root = nil
    self._radius = nil
    self._arc = nil
    self._height = nil
end

function MeleeArcPreview:_addAnchor(root: BasePart, position: Vector3): Attachment
    local item = attachment(root, position)
    table.insert(self._anchors, item)
    return item
end

function MeleeArcPreview:_addBeam(name: string, startAnchor: Attachment, endAnchor: Attachment,
    width: number, opacity: number)
    table.insert(self._beams, beam(self._folder, name, startAnchor, endAnchor, width, opacity))
end

function MeleeArcPreview:_build(root: BasePart, radius: number, arc: number)
    self:_clearGeometry()
    self._root, self._radius, self._arc, self._height = root, radius, arc, root.Size.Y
    -- Only a debug outline, not the server's contact plane. The contour sits
    -- at the RootCollider's foot and follows jumping/turning without a raycast.
    local footY = -root.Size.Y * 0.5
    local halfAngle = math.rad(arc) * 0.5
    local width = math.max(0.04, 2 * radius * math.sin(math.rad(arc) / (SEGMENTS * 2)) * 0.14)
    local ring = table.create(SEGMENTS + 1)
    for i = 0, SEGMENTS do
        local angle = -halfAngle + i / SEGMENTS * math.rad(arc)
        local direction = CFrame.fromAxisAngle(Vector3.yAxis, angle):VectorToWorldSpace(Vector3.new(0, 0, -1))
        ring[i + 1] = self:_addAnchor(root, Vector3.new(direction.X * radius, footY, direction.Z * radius))
    end
    for i = 1, SEGMENTS do
        self:_addBeam(("Segment%02d"):format(i), ring[i], ring[i + 1], width, 0.18)
    end
    local center = self:_addAnchor(root, Vector3.new(0, footY, 0))
    for index, endpoint in ipairs({ring[1], ring[SEGMENTS + 1]}) do
        self:_addBeam(("Boundary%02d"):format(index), center, endpoint, 0.065, 0.24)
        local arcAngle = if index == 1 then -halfAngle else halfAngle
        local direction = CFrame.fromAxisAngle(Vector3.yAxis, arcAngle):VectorToWorldSpace(Vector3.new(0, 0, -1))
        local lower = self:_addAnchor(root, Vector3.new(direction.X * radius, -math.max(3, root.Size.Y) * 0.5 - 1.5, direction.Z * radius))
        local upper = self:_addAnchor(root, Vector3.new(direction.X * radius, math.max(3, root.Size.Y) * 0.5 + 1.5, direction.Z * radius))
        self:_addBeam(("Boundary%02d"):format(index + 2), lower, upper, 0.08, 0.35)
    end
end

function MeleeArcPreview:_renderAimRay()
    local character = Players.LocalPlayer.Character
    local root = character and character:FindFirstChild("RootCollider")
    local ray = self._aimRay
    if not root or not root:IsA("BasePart")
        or string.lower(tostring(character:GetAttribute("EquippedWeaponType") or "")) == "bow" then
        if self._root then self:_clearGeometry() end
        ray.Transparency = 1
        return
    end
    local radius = math.max(1, tonumber(character:GetAttribute("AttackRadius")) or 7)
    local arc = math.clamp(tonumber(character:GetAttribute("MeleeArcAngle")) or 108, 1, 360)
    if self._root ~= root or self._radius ~= radius or self._arc ~= arc or self._height ~= root.Size.Y then
        self:_build(root, radius, arc)
    end
    local camera = Workspace.CurrentCamera
    if not camera then
        ray.Transparency = 1
        return
    end
    local origin, direction = camera.CFrame.Position, camera.CFrame.LookVector
    local depth = (root.Position - origin):Dot(direction)
    -- The original neon Part could cross the camera plane and look like
    -- a periodic impact spark even without any damage/effect event.
    if depth < 0.75 then
        ray.Transparency = 1
        return
    end
    local start = origin + direction * depth
    ray.Size = Vector3.new(0.045, 0.045, radius)
    ray.CFrame = CFrame.lookAt(start + direction * radius * 0.5, start + direction * radius)
    ray.Transparency = 0.55
end

function MeleeArcPreview:SetVisible(visible: boolean)
    visible = visible == true
    if visible == self._visible then return end
    self._visible = visible
    self._folder.Parent = if visible then Workspace else nil
    if visible then
        self._connection = RunService.RenderStepped:Connect(function()
            self:_renderAimRay()
        end)
    else
        if self._connection then
            self._connection:Disconnect()
            self._connection = nil
        end
        self:_clearGeometry()
    end
end

function MeleeArcPreview:Destroy()
    self:SetVisible(false)
    self._folder:Destroy()
end

return MeleeArcPreview
