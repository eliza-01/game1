local Players = game:GetService("Players")
local RunService = game:GetService("RunService")

local HairAttachmentController = {}
local started = false
local cache = setmetatable({}, { __mode = "k" })
local HAIR_GRIP_NAME = "CharacterMount"

type HairState = {
    hair: MeshPart,
    targetBone: Bone,
    grip: Attachment,
    targetName: string,
}

local function findState(character: Model): HairState?
    local hair: MeshPart? = nil
    for _, descendant in character:GetDescendants() do
        if descendant:IsA("MeshPart") and descendant:GetAttribute("Game1HairAttachment") == true then
            hair = descendant
            break
        end
    end
    if not hair then
        return nil
    end

    local targetName = tostring(hair:GetAttribute("HairTargetBoneName") or "")
    local target = character:FindFirstChild(targetName, true)
    local grip = hair:FindFirstChild(HAIR_GRIP_NAME)
    if not target or not target:IsA("Bone") or not grip or not grip:IsA("Attachment") then
        return nil
    end
    return {
        hair = hair,
        targetBone = target,
        grip = grip,
        targetName = targetName,
    }
end

local function targetSocketCFrame(targetBone: Bone): CFrame
    local parent = targetBone.Parent
    if parent and parent:IsA("Bone") then
        return parent.TransformedWorldCFrame * targetBone.CFrame
    end
    return targetBone.WorldCFrame
end

local function updateCharacter(character: Model)
    local state: HairState? = cache[character]
    if not state
        or not state.hair.Parent
        or not state.targetBone.Parent
        or not state.grip.Parent
        or state.targetName ~= tostring(state.hair:GetAttribute("HairTargetBoneName") or "")
    then
        state = findState(character)
        cache[character] = state
    end
    if not state then
        return
    end

    local socketFrame = targetSocketCFrame(state.targetBone)
    local delta = socketFrame * state.grip.WorldCFrame:Inverse()
    state.hair:PivotTo(delta * state.hair:GetPivot())
end

local function update()
    for _, player in Players:GetPlayers() do
        if player.Character then
            updateCharacter(player.Character)
        end
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

function HairAttachmentController.Start()
    if started then
        return
    end
    started = true
    RunService.RenderStepped:Connect(update)
end

return HairAttachmentController
