--!strict
-- Single client-side follower for anchored weapon and rigid hair models.
-- Weapon and hair use the same mount/pose solver, rather than separate
-- physics attachments or independent RenderStepped controllers.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local BoneModelMount = require(ReplicatedStorage:WaitForChild("Game1Shared")
    :WaitForChild("rig"):WaitForChild("BoneModelMount"))

local BoneMountedAttachmentController = {}
local started = false
local cache = setmetatable({}, { __mode = "k" })

type MountState = {
    character: Model,
    bone: Bone,
    grip: Attachment,
    targetName: string,
    kind: string,
}

local function resolveMount(model: Model, kind: string): (string?, string?)
    if kind == "weapon" then
        if model:GetAttribute("Game1WeaponAttachment") ~= true then return nil end
        return tostring(model:GetAttribute("WeaponTargetBoneName") or ""), "Game1WeaponGrip"
    end
    if model:GetAttribute("Game1HairCompound") ~= true then return nil end
    local root = model.PrimaryPart
    if not root or root:GetAttribute("Game1HairAttachment") ~= true then return nil end
    return tostring(root:GetAttribute("HairTargetBoneName") or ""), "CharacterMount"
end

local function updateMount(character: Model, model: Model, kind: string)
    local name, gripName = resolveMount(model, kind)
    if not name or name == "" or not gripName then return end
    local state: MountState? = cache[model]
    if not state or state.character ~= character or state.kind ~= kind
        or state.targetName ~= name or not state.bone.Parent or not state.grip.Parent then
        local bone = BoneModelMount.FindBone(character, name)
        local grip = model:FindFirstChild(gripName, true)
        if not bone or not grip or not grip:IsA("Attachment") then
            cache[model] = nil
            return
        end
        state = { character = character, bone = bone, grip = grip, targetName = name, kind = kind }
        cache[model] = state
    end
    BoneModelMount.Place(model, state.grip, BoneModelMount.SocketFrame(state.bone, kind))
end

local function findHairModel(character: Model): Model?
    -- Normal assembled characters have a fixed path; avoid full descendant
    -- scans every frame. Preview rigs may have ImportedRig at the root.
    local visual = character:FindFirstChild("Visual") or character
    local imported = visual:FindFirstChild("ImportedRig") or visual
    local group = imported:FindFirstChild("CharacterHairComponent")
    return if group and group:IsA("Model") then group else nil
end

local function updateCharacter(character: Model)
    local hair = findHairModel(character)
    if hair then updateMount(character, hair, "hair") end
    for _, weaponName in { "EquippedWeapon", "EquippedWeaponRight", "EquippedWeaponLeft" } do
        local weapon = character:FindFirstChild(weaponName)
        if weapon and weapon:IsA("Model") then
            updateMount(character, weapon, "weapon")
        end
    end
end

local function update()
    for _, player in Players:GetPlayers() do
        if player.Character then updateCharacter(player.Character) end
    end
    local npcs = workspace:FindFirstChild("NPCs")
    if npcs then
        for _, npc in npcs:GetChildren() do
            if npc:IsA("Model") and npc:GetAttribute("Game1NpcRuntime") == true then
                updateCharacter(npc)
            end
        end
    end
end

-- The Studio timeline preview shares the exact mount method without starting
-- a render connection. Scrubbing updates both weapons and pivot hair once.
BoneMountedAttachmentController.UpdateCharacter = updateCharacter

function BoneMountedAttachmentController.GetBowReleaseOrigin(character: Model): Vector3?
    local weapon = character:FindFirstChild("EquippedWeapon")
    if not weapon or not weapon:IsA("Model") or weapon:GetAttribute("WeaponType") ~= "bow" then
        return nil
    end
    for _, name in { "ArrowNock", "ArrowRelease", "ArrowSocket" } do
        local node = weapon:FindFirstChild(name, true)
        if node and node:IsA("Attachment") then return node.WorldPosition end
        if node and node:IsA("Bone") then return node.TransformedWorldCFrame.Position end
    end
    local state: MountState? = cache[weapon]
    if not state then
        updateMount(character, weapon, "weapon")
        state = cache[weapon]
    end
    return if state and state.bone.Parent then state.bone.TransformedWorldCFrame.Position else nil
end

function BoneMountedAttachmentController.Start()
    if started then return end
    started = true
    RunService.RenderStepped:Connect(update)
end

return BoneMountedAttachmentController
