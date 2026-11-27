--!strict
-- Local-only 3D avatars: one real assembly model for each ready Human preset.
-- Server publishes bound templates, client owns placement, color and animation.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")
local RunService = game:GetService("RunService")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local FaceMaterials = require(Shared:WaitForChild("character"):WaitForChild("CharacterCreationMaterials"))
local CharacterAnimationRegistry = require(Shared:WaitForChild("character"):WaitForChild("CharacterAnimationRegistry"))
local StageVisibility = require(script.Parent:WaitForChild("CharacterCreationStageVisibility"))
local BoneModelMount = require(Shared:WaitForChild("rig"):WaitForChild("BoneModelMount"))
local Mounts = require(script.Parent:WaitForChild("BoneMountedAttachmentController"))
local MeshPreloader = require(script.Parent:WaitForChild("CharacterCreationMeshPreloader"))
local Turntable = require(script.Parent:WaitForChild("CharacterPreviewTurntable"))
local Reactions = require(script.Parent:WaitForChild("CharacterCreationReactions"))
local Controller = {}
Controller.__index = Controller

local function stageFolder(): Instance?
    local places = Workspace:FindFirstChild("Places")
    return places and places:FindFirstChild("Character Creation")
end

-- CharacterSelectionPreviewPoint comes from the same resolved pair as the camera.
local function asCFrame(settings: any, gender: string, stage: string?, anchors: any?): CFrame?
    if stage == "selection" and anchors then return anchors.preview end
    local scene = stageFolder()
    local markerName = if gender == "male" then "MalePreviewPoint" else "FemalePreviewPoint"
    if settings.useStudioSpawnMarkers ~= false and scene then
        local group = scene:FindFirstChild("Game1CharacterCreationSpawnPoints") or scene
        local point = group:FindFirstChild(markerName, true)
        if point and (point:IsA("Model") or point:IsA("BasePart")) then
            return point:GetPivot()
        end
    end
    local row = (settings.spawnPoints or {})[gender]
    if type(row) ~= "table" then return nil end
    local p = row.position
    local r = row.rotationDegrees
    if type(p) ~= "table" or type(r) ~= "table" or #p ~= 3 or #r ~= 3 then return nil end
    for _, coordinate in ipairs(p) do
        if type(coordinate) ~= "number" or coordinate ~= coordinate or math.abs(coordinate) > 100000 then
            return nil
        end
    end
    for _, angle in ipairs(r) do
        if type(angle) ~= "number" or angle ~= angle or math.abs(angle) > 100000 then
            return nil
        end
    end
    return CFrame.new(p[1], p[2], p[3])
        * CFrame.Angles(math.rad(r[1]), math.rad(r[2]), math.rad(r[3]))
end

local function paint(model: Model, colors: any)
    local eyes = colors.eyes or {}
    local brows = colors.eyebrows
    local hair = colors.hair or {}
    for _, object in ipairs(model:GetDescendants()) do
        if object:IsA("MeshPart") then
            local slot = object:GetAttribute("CharacterPartSlot")
            local channel = object:GetAttribute("HairColorChannel")
            local color: string? = nil
            if slot == "eye_l" then color = eyes.l
            elseif slot == "eye_r" then color = eyes.r
            elseif slot == "eyebrow_l" or slot == "eyebrow_r" then color = brows
            elseif type(channel) == "string" then color = hair[channel] end
            if color then
                local tint = Color3.fromRGB(
                    tonumber(string.sub(color, 2, 3), 16) or 0,
                    tonumber(string.sub(color, 4, 5), 16) or 0,
                    tonumber(string.sub(color, 6, 7), 16) or 0)
                local surface = object:FindFirstChildOfClass("SurfaceAppearance")
                if surface then surface.Color = tint else object.Color = tint end
            end
        end
    end
end

local function applyMaterials(model: Model, materials: any)
    if type(materials) ~= "table" then return end
    for _, object in ipairs(model:GetDescendants()) do
        if object:IsA("MeshPart") then
            local slot = object:GetAttribute("CharacterPartSlot")
            local channel = object:GetAttribute("HairColorChannel")
            local group = FaceMaterials.GroupForPart(slot, channel)
            local materialName = if group then materials[group] else nil
            if type(materialName) == "string" then
                local material = Enum.Material[materialName]
                if material then object.Material = material end
            end
        end
    end
end

local function playIdle(model: Model, archetype: string): AnimationTrack?
    local profile = (CharacterAnimationRegistry.profiles or {})[archetype]
    local tracks = profile and profile.weapons and profile.weapons.hands and profile.weapons.hands.idle
    local clip = tracks and tracks[1]
    if not clip or type(clip.animationId) ~= "string" then return nil end
    local animator = model:FindFirstChildWhichIsA("Animator", true)
    if not animator then return nil end
    local animation = Instance.new("Animation")
    animation.Name = "CharacterCreationIdle"
    animation.AnimationId = clip.animationId
    animation.Parent = model
    local ok, track = pcall(function() return animator:LoadAnimation(animation) end)
    if ok and track then
        track.Looped = true
        track.Priority = Enum.AnimationPriority.Idle
        track:Play(0)
        return track
    end
    animation:Destroy()
    warn("[game1][character-creation] idle load failed: " .. tostring(track))
    return nil
end

function Controller.new(settings: any, canRotate: () -> boolean, freeTarget: (() -> (string?, boolean))?)
    local localFolder = Instance.new("Folder")
    localFolder.Name = "Game1CharacterCreationLocalPreviews"
    localFolder.Parent = Workspace
    local hidden = StageVisibility.Hide(stageFolder())
    local models: {[string]: Model} = {}
    return setmetatable({settings = settings, folder = localFolder, models = models,
        hidden = hidden, tracks = {} :: {[string]: AnimationTrack},
        reactions = Reactions.new(settings.animations),
        turntable = Turntable.new(models, canRotate, freeTarget)}, Controller)
end

local function templateReady(template: Model): boolean
    local count = template:GetAttribute("Game1PreviewDescendantCount")
    if type(count) ~= "number" or count ~= #template:GetDescendants() or not template.PrimaryPart then return false end
    local imported = template:FindFirstChild("ImportedRig")
    if not imported or not imported:FindFirstChild("rig_carrier") then return false end
    local expected = template:GetAttribute("Game1AssemblyHairPieceCount")
    if type(expected) ~= "number" then return false end
    local hair = imported:FindFirstChild("CharacterHairComponent")
    if expected == 0 then return hair == nil end
    if not hair or not hair:IsA("Model") or hair:GetAttribute("Game1HairPieceCount") ~= expected
        or not BoneModelMount.HairReady(hair) then return false end
    local root = hair.PrimaryPart
    local name = root and root:GetAttribute("HairTargetBoneName")
    return type(name) == "string" and BoneModelMount.FindHairBone(template, name) ~= nil
end

function Controller.AwaitTemplate(templateName: string, isCurrent: (() -> boolean)?): Model?
    local replicationDeadline = os.clock() + 15
    local template: Instance? = nil
    repeat
        if isCurrent and not isCurrent() then return nil end
        local available = ReplicatedStorage:FindFirstChild("Game1CharacterCreationTemplates")
        template = available and available:FindFirstChild(templateName)
        if template then break end
        task.wait(0.1)
    until os.clock() >= replicationDeadline
    if not template or not template:IsA("Model") or (isCurrent and not isCurrent()) then return nil end
    while not templateReady(template) do
        if not template.Parent or (isCurrent and not isCurrent()) then return nil end
        if os.clock() >= replicationDeadline then
            warn("[game1][character-creation] incomplete preview template: " .. templateName)
            return nil
        end
        RunService.Heartbeat:Wait()
    end
    return template
end

function Controller:Set(archetype: string, templateName: string, choice: any, stage: string?, isCurrent: (() -> boolean)?, anchors: any?, onPreloadProgress: ((number) -> ())?): boolean
    local template = Controller.AwaitTemplate(templateName, isCurrent)
    if not self.folder.Parent or not template then return false end
    if isCurrent and not isCurrent() then return false end
    local gender = if archetype == "human_male" then "male" else "female"
    local target = asCFrame(self.settings, gender, stage, anchors)
    local other = asCFrame(self.settings, if gender == "male" then "female" else "male")
    if not target or not other then
        warn("[game1][character-creation] missing or invalid authored spawn points: " .. gender)
        return false
    end
    if stage ~= "selection" and (target.Position - other.Position).Magnitude < 2 then
        warn("[game1][character-creation] Male/Female spawn points overlap")
        return false
    end
    local instance = template:Clone()
    if not templateReady(instance) then instance:Destroy(); return false end
    local visibility: {[BasePart]: number} = {}
    instance.Name = archetype .. "Preview"
    for _, object in ipairs(instance:GetDescendants()) do
        if object:IsA("BasePart") then
            visibility[object] = object.LocalTransparencyModifier
            object.LocalTransparencyModifier = 1
            object.Anchored = true
            object.CanCollide = false
            object.CanTouch = false
            object.CanQuery = false
        end
    end
    instance:PivotTo(target)
    print(string.format("[game1][character-creation] %s preview positioned (%.3f, %.3f, %.3f), yaw %.3f",
        gender, target.Position.X, target.Position.Y, target.Position.Z, math.deg(select(2, target:ToOrientation()))))
    paint(instance, choice.colors or {})
    applyMaterials(instance, choice.materials or {})
    local complete, geometryReady = MeshPreloader.PreloadModel(instance, isCurrent, onPreloadProgress)
    if not geometryReady then
        instance:Destroy()
        return false
    end
    if not complete then warn("[game1][character-creation] texture preload incomplete; renderer will retry") end
    instance.Parent = self.folder
    Mounts.RegisterPreview(instance)
    local track = playIdle(instance, archetype)
    local function current(): boolean
        return self.folder.Parent ~= nil and (not isCurrent or isCurrent())
    end
    local function discard(): boolean
        Mounts.UnregisterPreview(instance)
        instance:Destroy()
        return false
    end
    local previousTrack = self.tracks[archetype]
    if track then
        local deadline = os.clock() + 10
        while current() and track.Length <= 0 and os.clock() < deadline do
            RunService.PreAnimation:Wait()
        end
        if not current() then return discard() end
        if track.Length <= 0 then
            warn("[game1][character-creation] idle animation not ready: " .. archetype)
            return discard()
        end
        -- Keep the old rig visible until the replacement is animated at the
        -- same phase. PreSimulation follows Animator evaluation (PreAnimation).
        RunService.PreAnimation:Wait()
        if not current() then return discard() end
        if previousTrack and previousTrack.Length > 0 then
            track.TimePosition = (previousTrack.TimePosition / previousTrack.Length % 1) * track.Length
        end
        RunService.PreSimulation:Wait()
    elseif previousTrack then
        warn("[game1][character-creation] refusing an unanimated replacement: " .. archetype)
        return discard()
    end
    if not current() then return discard() end
    -- Choices can change while the animation asset is loading.
    paint(instance, choice.colors or {})
    applyMaterials(instance, choice.materials or {})
    self.turntable:Place(archetype, instance, target)
    if not Mounts.UpdateCharacter(instance) then
        warn("[game1][character-creation] hair mount not ready: " .. archetype)
        return discard()
    end
    local previous = self.models[archetype]
    self.models[archetype] = instance
    self.tracks[archetype] = track
    if previous then self.reactions:Remove(previous); Mounts.UnregisterPreview(previous); previous:Destroy() end
    for part, transparency in pairs(visibility) do part.LocalTransparencyModifier = transparency end
    return true
end

function Controller:KeepOnly(archetype: string?)
    for id, model in pairs(self.models) do
        if id ~= archetype then
            self.reactions:Remove(model)
            Mounts.UnregisterPreview(model)
            model:Destroy()
            self.models[id] = nil
            self.tracks[id] = nil
            self.turntable:Remove(id)
        end
    end
end

function Controller:Colors(archetype: string, colors: any)
    local model = self.models[archetype]
    if model then paint(model, colors) end
end

function Controller:Materials(archetype: string, materials: any)
    local model = self.models[archetype]
    if model then applyMaterials(model, materials) end
end

function Controller:React(archetype: string)
    local model = self.models[archetype]
    if model then self.reactions:Play(model, archetype) end
end

function Controller:Destroy()
    self.reactions:Destroy()
    self.turntable:Destroy()
    for _, model in pairs(self.models) do Mounts.UnregisterPreview(model) end
    self.folder:Destroy()
    StageVisibility.Restore(self.hidden)
    table.clear(self.models)
    table.clear(self.tracks)
end
return Controller
