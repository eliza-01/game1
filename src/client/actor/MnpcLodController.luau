-- Per-client presentation for both dynamic actor kinds. Reuses the world's
-- Heartbeat; no per-actor frame loops. Server combat and navigation untouched.
local Players = game:GetService("Players")
local Workspace = game:GetService("Workspace")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local World = Shared:WaitForChild("world")
local Registry = require(World:WaitForChild("MnpcLodRegistry"))
local Policy = require(World:WaitForChild("MnpcLodPolicy"))
local AttackConfig = require(Shared:WaitForChild("combat"):WaitForChild("AttackConfig"))
local Mask = require(script.Parent:WaitForChild("MnpcLodMask"))
local Cache = require(script.Parent:WaitForChild("MnpcLodPrototypeCache"))
local Controller = {}
Controller.__index = Controller
local INTERVAL = 0.25
local TRANSITIONS = 4 -- one static part per operation; independent capped lane
local FOLDERS = {Monsters = "Monster", NPCs = "NPC"}
local function destroyPart(record)
    if record.part then record.part:Destroy(); record.part = nil end
    record.asset = nil
    record.boundRoot = nil
    record.boundCollider = nil
end
local function setStage(record, stage)
    if record.actual ~= stage then
        record.actual = stage
        record.model:SetAttribute("Game1MnpcLocalLod", stage)
    end
end
local function unmask(record)
    if record.mask then record.mask:Destroy(); record.mask = nil end
end
local function hide(record)
    if not record.mask then record.mask = Mask.new(record.model) end
end
local function createPart(folder, record, root, collider, prototype, asset)
    local part = prototype and prototype:Clone() or Instance.new("Part")
    part.Name = prototype and "MNPC_LOD1" or "MNPC_LOD1_RED_DUMMY"
    if prototype then
        part.CFrame = root.CFrame * CFrame.new(table.unpack(asset.rootCFrame))
    else
        part.Color = Color3.fromRGB(220, 35, 35)
        part.Material = Enum.Material.SmoothPlastic
        part.Size = collider and collider.Size or Vector3.new(2, 4, 2)
        part.CFrame = collider and collider.CFrame or root.CFrame * CFrame.new(0, -0.8, 0)
    end
    part.Anchored = false
    part.CanCollide = false
    part.CanTouch = false
    part.CanQuery = false
    part.Massless = true
    part.CastShadow = false
    part.RootPriority = -127
    local weld = Instance.new("WeldConstraint")
    weld.Part0 = root
    weld.Part1 = part
    weld.Parent = part
    part.Parent = folder
    -- Commit before retiring previous representation. No yield.
    destroyPart(record)
    record.part, record.boundRoot, record.boundCollider, record.asset = part, root, collider, prototype and asset or nil
end
local function rootOf(model, name)
    local root = model:FindFirstChild(name)
    return root and root:IsA("BasePart") and root or nil
end
local function fullReady(model)
    local rig = model:FindFirstChild("ImportedRig")
    local stage = model:GetAttribute("Game1MnpcDemandStage")
    return (stage == nil or stage == "full") and model:GetAttribute("Game1MnpcRigReady") == true and rig and rig:IsA("Model")
        and rig:FindFirstChildWhichIsA("MeshPart", true) ~= nil
end
local function pinned(record, player, distance, profile, collider)
    local model = record.model
    local reach = math.clamp(tonumber(player.Character:GetAttribute("AttackRadius")) or AttackConfig.Range, 0, AttackConfig.MaxAimDistance)
    local extent = collider and collider.Size.Magnitude * 0.5 or 0
    return distance <= reach + extent + 8
        or (record.actual == "FULL" and distance < profile.hide and model:GetAttribute("LifeState") ~= "Alive")
        or model:GetAttribute("MonsterTargetUserId") == player.UserId
        or model:GetAttribute("NpcTargetUserId") == player.UserId
        or model:GetAttribute("Game1GameplayTestOwner") ~= nil
end
function Controller:_remove(model)
    local record = self.records[model]
    if not record then return end
    self.records[model] = nil
    destroyPart(record)
    unmask(record)
    model:SetAttribute("Game1MnpcLocalLod", nil)
end
function Controller:_add(model, kind)
    if not model:IsA("Model") or self.records[model] then return end
    self.records[model] = {model = model, kind = kind}
end
function Controller:_watch(folder, kind)
    if self.folders[kind] then self:_unwatch(kind) end
    self.folders[kind] = {folder = folder, connections = {
        folder.ChildAdded:Connect(function(model) self:_add(model, kind) end),
        folder.ChildRemoved:Connect(function(model) self:_remove(model) end),
    }}
    for _, model in ipairs(folder:GetChildren()) do self:_add(model, kind) end
end
function Controller:_unwatch(kind)
    local watched = self.folders[kind]
    if not watched then return end
    self.folders[kind] = nil
    for _, connection in ipairs(watched.connections) do connection:Disconnect() end
    for model, record in pairs(self.records) do
        if record.kind == kind then self:_remove(model) end
    end
end
function Controller.new()
    local self = setmetatable({records = {}, folders = {}, elapsed = INTERVAL, pending = {}, cursor = 1,
        cache = Cache.new()}, Controller)
    self.folder = Instance.new("Folder")
    self.folder.Name = "Game1MnpcClientVisuals"
    self.folder.Parent = Workspace
    local function added(node)
        if FOLDERS[node.Name] and node:IsA("Folder") then self:_watch(node, FOLDERS[node.Name]) end
    end
    self.added = Workspace.ChildAdded:Connect(added)
    self.removed = Workspace.ChildRemoved:Connect(function(node)
        local kind = FOLDERS[node.Name]
        if kind and self.folders[kind] and self.folders[kind].folder == node then self:_unwatch(kind) end
    end)
    for name in pairs(FOLDERS) do
        local folder = Workspace:FindFirstChild(name)
        if folder then added(folder) end
    end
    return self
end
function Controller:_observe(player, root)
    self.pending = {}
    self.cursor = 1
    local wantedKeys = {}
    for model, record in pairs(self.records) do
        local actorRoot = rootOf(model, "HumanoidRootPart")
        local collider = rootOf(model, "RootCollider")
        local slug = model:GetAttribute(record.kind == "NPC" and "NpcSlug" or "MonsterSlug")
        local key = Policy.Key(record.kind, slug)
        local entry = key and Registry.actors[key]
        local profile = entry and entry.profile or Registry.defaults
        local ready = actorRoot and key and model:GetAttribute("Game1MnpcKind") == record.kind
            and model:GetAttribute("LifeState") ~= nil and Policy.Valid(profile)
        if not ready then
            destroyPart(record); unmask(record); setStage(record, nil)
            record.desired = nil
        else
            local distance = (actorRoot.Position - root.Position).Magnitude
            local desired = Policy.Resolve(distance, record.desired, profile, pinned(record, player, distance, profile, collider))
            record.desired, record.distance = desired, distance
            record.root, record.collider, record.key = actorRoot, collider, key
            -- Keep a visible placeholder if server is still building FULL.
            -- Explicit opt-out/test actors remain on their original FULL path.
            local actual = desired
            if desired == "FULL" and profile.enabled and model:GetAttribute("Game1GameplayTestOwner") == nil
                and model:GetAttribute("LifeState") == "Alive" and model:GetAttribute("MonsterSpawning") ~= true
                and not fullReady(model) then actual = "LOD1" end
            record.target = actual
            record.lifeState = model:GetAttribute("LifeState")
            local asset = entry and entry.asset
            if asset and tostring(model:GetAttribute("Game1MnpcFullModelId") or "") ~= asset.fullModelId then asset = nil end
            record.wantedAsset = asset
            if actual == "LOD1" and asset then wantedKeys[key] = true end
            if actual ~= record.actual or (actual == "LOD1" and (record.boundRoot ~= actorRoot
                or record.boundCollider ~= collider or not record.part or (asset and record.asset ~= asset) or (not asset and record.asset))) then
                self.pending[#self.pending + 1] = record
            end
        end
    end
    self.cache:YieldOutside(wantedKeys)
    table.sort(self.pending, function(a, b) return a.distance < b.distance end)
end
function Controller:Step(dt)
    local player = Players.LocalPlayer
    local root = player.Character and rootOf(player.Character, "HumanoidRootPart")
    if not root then
        self.playerRoot = nil
        return
    end
    self.elapsed = self.elapsed + dt
    if self.elapsed >= INTERVAL or root ~= self.playerRoot
        or not self.lastPosition or (root.Position - self.lastPosition).Magnitude >= 64 then
        self.elapsed, self.playerRoot, self.lastPosition = 0, root, root.Position
        self:_observe(player, root)
    end
    local count, checked = 0, 0
    while self.cursor <= #self.pending and count < TRANSITIONS and checked < 16 do
        local record = self.pending[self.cursor]
        self.cursor = self.cursor + 1
        checked = checked + 1
        if self.records[record.model] == record and record.root.Parent then
            if record.model:GetAttribute("LifeState") ~= record.lifeState then
                self.elapsed = INTERVAL
            else
                local target = record.target
                if target == "FULL" then
                    unmask(record); destroyPart(record); setStage(record, "FULL")
                elseif target == "UNLOADED" then
                    hide(record); destroyPart(record); setStage(record, "UNLOADED")
                else
                    local prototype = self.cache:Get(record.key, record.wantedAsset)
                    if not record.part or record.boundRoot ~= record.root or record.boundCollider ~= record.collider
                        or (prototype and record.asset ~= record.wantedAsset) or (record.asset and not record.wantedAsset) then
                        createPart(self.folder, record, record.root, record.collider, prototype, record.wantedAsset)
                    end
                    hide(record); setStage(record, "LOD1")
                end
                count = count + 1
            end
        end
    end
end
function Controller:Destroy()
    if self.destroyed then return end
    self.destroyed = true
    self.added:Disconnect(); self.removed:Disconnect()
    for kind in pairs(self.folders) do self:_unwatch(kind) end
    self.cache:Destroy(); self.folder:Destroy()
end
return Controller
