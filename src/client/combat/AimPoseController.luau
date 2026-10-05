local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local AttackConfig = require(CombatShared:WaitForChild("AttackConfig"))

local AimPoseController = {}

local localPlayer = Players.LocalPlayer
local started = false
local character: Model? = nil
local root: BasePart? = nil
local torsoBones: { Bone } = {}
local previousProcedural: { [Bone]: CFrame } = {}
local targetPosition: Vector3? = nil
local activeUntil = 0
local renderedYaw = 0

local PREFERRED_SPINE_NAMES = {
    "spine.001",
    "spine.002",
    "spine.003",
}

local RETICLE_GUI_NAME = "Game1AimReticle"

local function ensureReticle()
    local playerGui = localPlayer:WaitForChild("PlayerGui")
    local existing = playerGui:FindFirstChild(RETICLE_GUI_NAME)
    if existing then
        return
    end

    local gui = Instance.new("ScreenGui")
    gui.Name = RETICLE_GUI_NAME
    gui.IgnoreGuiInset = true
    gui.ResetOnSpawn = false
    gui.DisplayOrder = 50

    local dot = Instance.new("Frame")
    dot.Name = "Dot"
    dot.AnchorPoint = Vector2.new(0.5, 0.5)
    dot.Position = UDim2.fromScale(0.5, 0.5)
    dot.Size = UDim2.fromOffset(5, 5)
    dot.BackgroundColor3 = Color3.fromRGB(245, 245, 245)
    dot.BorderSizePixel = 0
    dot.Parent = gui

    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(1, 0)
    corner.Parent = dot

    local stroke = Instance.new("UIStroke")
    stroke.Color = Color3.fromRGB(20, 20, 20)
    stroke.Thickness = 1
    stroke.Transparency = 0.15
    stroke.Parent = dot

    gui.Parent = playerGui
end

local function flatUnit(direction: Vector3): Vector3?
    local flat = Vector3.new(direction.X, 0, direction.Z)
    if flat.Magnitude <= 0.001 then
        return nil
    end
    return flat.Unit
end

local function signedYaw(fromDirection: Vector3, toDirection: Vector3): number
    local from = flatUnit(fromDirection)
    local to = flatUnit(toDirection)
    if not from or not to then
        return 0
    end
    return math.atan2(from:Cross(to).Y, math.clamp(from:Dot(to), -1, 1))
end

local function spineOrder(name: string): number?
    local lower = string.lower(name)
    if lower == "spine" then
        return 0
    end
    local suffix = string.match(lower, "^spine%.(%d+)$")
    if suffix then
        return tonumber(suffix)
    end
    return nil
end

local function findTorsoBones(model: Model): { Bone }
    local visual = model:FindFirstChild("Visual")
    if not visual then
        return {}
    end

    local preferred = {}
    for _, name in ipairs(PREFERRED_SPINE_NAMES) do
        local found = visual:FindFirstChild(name, true)
        if found and found:IsA("Bone") then
            table.insert(preferred, found)
        end
    end
    if #preferred == #PREFERRED_SPINE_NAMES then
        return preferred
    end

    local candidates = {}
    for _, descendant in visual:GetDescendants() do
        if descendant:IsA("Bone") then
            local order = spineOrder(descendant.Name)
            if order ~= nil then
                table.insert(candidates, { bone = descendant, order = order })
            end
        end
    end
    table.sort(candidates, function(left, right)
        return left.order < right.order
    end)

    -- Keep the pelvis/root spine untouched. The first three descendants above it
    -- form the universal upper-body twist chain for the imported Lineage rigs.
    local result = {}
    for _, candidate in ipairs(candidates) do
        if candidate.order >= 1 then
            table.insert(result, candidate.bone)
            if #result >= 3 then
                break
            end
        end
    end
    return result
end

local function clearCharacter()
    character = nil
    root = nil
    torsoBones = {}
    targetPosition = nil
    activeUntil = 0
    renderedYaw = 0
    table.clear(previousProcedural)
end

local function bindCharacter(newCharacter: Model)
    clearCharacter()
    character = newCharacter
    local newRoot = newCharacter:WaitForChild("RootCollider", 10)
    if not newRoot or not newRoot:IsA("BasePart") then
        warn("[game1][aim] RootCollider is missing")
        return
    end
    root = newRoot
    torsoBones = findTorsoBones(newCharacter)
    if #torsoBones == 0 then
        warn("[game1][aim] no compatible spine chain; root facing still works")
    else
        local names = {}
        for _, bone in ipairs(torsoBones) do
            table.insert(names, bone.Name)
        end
        print(("[game1][aim] torso chain ready: %s"):format(table.concat(names, " -> ")))
    end
end

local function restorePreviousProcedural()
    for bone, delta in pairs(previousProcedural) do
        if bone.Parent then
            -- Procedural rotation is layered as delta * animationTransform below.
            -- Remove exactly our previous layer before Animator evaluates again.
            bone.Transform = delta:Inverse() * bone.Transform
        end
    end
    table.clear(previousProcedural)
end

local function desiredTorsoYaw(now: number): number
    local currentRoot = root
    local target = targetPosition
    if not currentRoot or not currentRoot.Parent or not target or now > activeUntil then
        return 0
    end

    local aim = flatUnit(target - currentRoot.Position)
    local forward = flatUnit(currentRoot.CFrame.LookVector)
    if not aim or not forward then
        return 0
    end

    return math.clamp(
        signedYaw(forward, aim),
        -AttackConfig.TorsoYawLimit,
        AttackConfig.TorsoYawLimit
    )
end

local function applyPose(deltaTime: number)
    local now = os.clock()
    local desired = desiredTorsoYaw(now)
    local response = math.max(1, AttackConfig.TorsoAimResponse)
    local blend = 1 - math.exp(-response * math.max(0, deltaTime))
    renderedYaw += (desired - renderedYaw) * blend
    if math.abs(renderedYaw) < 0.0001 and desired == 0 then
        renderedYaw = 0
    end

    local count = #torsoBones
    if count > 0 and math.abs(renderedYaw) > 0.00001 then
        local perBoneYaw = renderedYaw / count
        for _, bone in ipairs(torsoBones) do
            if bone.Parent then
                local delta = CFrame.Angles(0, perBoneYaw, 0)
                -- PreSimulation runs after Animator has produced this frame's pose,
                -- so the procedural twist layers on top instead of replacing attack
                -- animation transforms.
                bone.Transform = delta * bone.Transform
                previousProcedural[bone] = delta
            end
        end
    end

    if character then
        character:SetAttribute("AimTorsoYawDegrees", math.deg(renderedYaw))
        character:SetAttribute("AimPoseActive", targetPosition ~= nil and now <= activeUntil)
    end
end

function AimPoseController.GetAimPosition(): Vector3?
    local camera = Workspace.CurrentCamera
    if not camera then
        return nil
    end

    -- RobloxLineage uses one center-screen reticle for both presentation and the
    -- attack intent. Never derive body facing from a second cursor-space ray.
    local viewport = camera.ViewportSize
    local ray = camera:ViewportPointToRay(viewport.X * 0.5, viewport.Y * 0.5)
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = character and { character } or {}
    local hit = Workspace:Raycast(ray.Origin, ray.Direction * AttackConfig.MaxAimDistance, params)
    return if hit then hit.Position else ray.Origin + ray.Direction * AttackConfig.MaxAimDistance
end

function AimPoseController.BeginAttack(target: Vector3, duration: number)
    if typeof(target) ~= "Vector3" then
        return
    end
    targetPosition = target
    activeUntil = os.clock() + math.max(0.05, tonumber(duration) or 0.05)
end

function AimPoseController.UpdateTarget(target: Vector3)
    if typeof(target) == "Vector3" and os.clock() <= activeUntil then
        targetPosition = target
    end
end

function AimPoseController.EndAttack()
    targetPosition = nil
    activeUntil = 0
end

function AimPoseController.Start()
    if started then
        return
    end
    started = true
    task.spawn(ensureReticle)

    localPlayer.CharacterAdded:Connect(bindCharacter)
    localPlayer.CharacterRemoving:Connect(function(removing)
        if removing == character then
            clearCharacter()
        end
    end)
    if localPlayer.Character then
        task.spawn(bindCharacter, localPlayer.Character)
    end

    RunService.PreAnimation:Connect(restorePreviousProcedural)
    RunService.PreSimulation:Connect(applyPose)
end

return AimPoseController
