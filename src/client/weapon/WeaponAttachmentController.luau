local Players = game:GetService("Players")
local RunService = game:GetService("RunService")

local WeaponAttachmentController = {}
local started = false
local cache = setmetatable({}, { __mode = "k" })
local WEAPON_GRIP_NAME = "Game1WeaponGrip"
local WEAPON_EQUIP_ROTATION = CFrame.Angles(math.rad(-90), 0, 0)

local function findNamedBone(root: Instance, name: string): Bone?
    if name == "" then
        return nil
    end
    local found = root:FindFirstChild(name, true)
    return if found and found:IsA("Bone") then found else nil
end

local function findWeaponGrip(weapon: Model): Attachment?
    local found = weapon:FindFirstChild(WEAPON_GRIP_NAME, true)
    return if found and found:IsA("Attachment") then found else nil
end

local function targetSocketCFrame(targetBone: Bone): CFrame
    local parent = targetBone.Parent
    if parent and parent:IsA("Bone") then
        return parent.TransformedWorldCFrame * targetBone.CFrame
    end
    return targetBone.WorldCFrame
end

local function buildState(character: Model, weapon: Model)
    local visual = character:FindFirstChild("Visual")
    if not visual then
        return nil
    end
    local targetName = tostring(weapon:GetAttribute("WeaponTargetBoneName") or "")
    local targetBone = findNamedBone(visual, targetName)
    if not targetBone then
        return nil
    end
    local grip = findWeaponGrip(weapon)
    if not grip then
        return nil
    end
    return {
        character = character,
        weapon = weapon,
        targetName = targetName,
        targetBone = targetBone,
        grip = grip,
    }
end

local function updateWeapon(character: Model, weapon: Model)
    local requestedName = tostring(weapon:GetAttribute("WeaponTargetBoneName") or "")
    local state = cache[weapon]
    if not state
        or state.character ~= character
        or not state.targetBone.Parent
        or state.targetName ~= requestedName
        or not state.grip.Parent
    then
        state = buildState(character, weapon)
        cache[weapon] = state
    end
    if state then
        local socketFrame = targetSocketCFrame(state.targetBone) * WEAPON_EQUIP_ROTATION
        -- Server creates the same canonical runtime grip for every weapon before
        -- parenting it to the character. The client has no legacy Model-pivot path.
        local delta = socketFrame * state.grip.WorldCFrame:Inverse()
        weapon:PivotTo(delta * weapon:GetPivot())
    end
end

local function update()
    for _, player in Players:GetPlayers() do
        local character = player.Character
        if character then
            local weapon = character:FindFirstChild("EquippedWeapon")
            if weapon and weapon:IsA("Model") and weapon:GetAttribute("Game1WeaponAttachment") == true then
                updateWeapon(character, weapon)
            end
        end
    end
end

function WeaponAttachmentController.Start()
    if started then
        return
    end
    started = true
    RunService.RenderStepped:Connect(update)
end

return WeaponAttachmentController
