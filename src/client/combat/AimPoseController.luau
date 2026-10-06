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
local aimBone: Bone? = nil
local previousProcedural: { [Bone]: CFrame } = {}
local targetPosition: Vector3? = nil
local activeUntil = 0
local renderedYaw = 0
local poseDrivenExternally = false
local skipOwnStepOnce = false

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

local function findAimBone(model: Model): Bone?
    local visual = model:FindFirstChild("Visual")
    if not visual then
        return nil
    end

    for _, name in ipairs(PREFERRED_SPINE_NAMES) do
        local found = visual:FindFirstChild(name, true)
        if found and found:IsA("Bone") then
            return found
        end
    end

    local candidates = {}
    for _, descendant in visual:GetDescendants() do
        if descendant:IsA("Bone") then
            local order = spineOrder(descendant.Name)
            if order ~= nil and order >= 1 then
                table.insert(candidates, { bone = descendant, order = order })
            end
        end
    end
    table.sort(candidates, function(left, right)
        return left.order < right.order
    end)
    return if candidates[1] then candidates[1].bone else nil
end

local function parentWorldCFrame(bone: Bone): CFrame?
    local parent = bone.Parent
    if not parent then
        return nil
    end
    if parent:IsA("Bone") then
        return parent.TransformedWorldCFrame
    end
    if parent:IsA("BasePart") then
        return parent.CFrame
    end
    return nil
end

local function clearCharacter()
    character = nil
    root = nil
    aimBone = nil
    targetPosition = nil
    activeUntil = 0
    renderedYaw = 0
    poseDrivenExternally = false
    skipOwnStepOnce = false
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
    aimBone = findAimBone(newCharacter)
    if not aimBone then
        warn("[game1][aim] no compatible upper-body aim pivot; root facing still works")
    else
        print(("[game1][aim] world-space aim pivot ready: %s"):format(aimBone.Name))
    end
end

local function restorePreviousProcedural()
    for bone, delta in pairs(previousProcedural) do
        if bone.Parent then
            -- Remove exactly the world-space layer written after the previous
            -- Animator evaluation. The next Animator pass is then free to produce
            -- the new attack/combat-idle source pose before aim is applied again.
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

local function applyWorldAim(bone: Bone, yaw: number)
    local currentRoot = root
    if not currentRoot or math.abs(yaw) <= 0.00001 then
        return
    end

    -- RobloxLineage applies aim in WORLD space at the first upper-body bridge,
    -- after Animator/source-attack composition. This avoids relying on imported
    -- Blender bone-local axes and leaves pelvis + both legs completely untouched.
    local parentWorld = parentWorldCFrame(bone)
    if not parentWorld then
        return
    end
    local animatedTransform = bone.Transform
    local animatedWorld = bone.TransformedWorldCFrame
    local position = animatedWorld.Position
    local animatedRotation = animatedWorld - position

    -- signedYaw() follows Roblox world handedness: a target to character-right
    -- produces negative yaw, which is also the world-Y rotation that turns -Z
    -- toward +X. Apply it directly; imported bone-local axes never enter the math.
    local yawRotation = CFrame.fromAxisAngle(Vector3.yAxis, yaw)
    local desiredWorld = CFrame.new(position) * (yawRotation * animatedRotation)

    local currentLocal = parentWorld:ToObjectSpace(animatedWorld)
    local effectiveBase = currentLocal * animatedTransform:Inverse()
    local desiredLocal = parentWorld:ToObjectSpace(desiredWorld)
    local desiredTransform = effectiveBase:Inverse() * desiredLocal
    local delta = desiredTransform * animatedTransform:Inverse()
    bone.Transform = delta * animatedTransform
    previousProcedural[bone] = delta
end

local function stepPose(deltaTime: number)
    local now = os.clock()
    local desired = desiredTorsoYaw(now)
    local response = math.max(1, AttackConfig.TorsoAimResponse)
    local blend = 1 - math.exp(-response * math.max(0, deltaTime))
    renderedYaw += (desired - renderedYaw) * blend
    if math.abs(renderedYaw) < 0.0001 and desired == 0 then
        renderedYaw = 0
    end

    local bone = aimBone
    if bone and bone.Parent then
        applyWorldAim(bone, renderedYaw)
    end

    if character then
        character:SetAttribute("AimTorsoYawDegrees", math.deg(renderedYaw))
        character:SetAttribute("AimPoseActive", targetPosition ~= nil and now <= activeUntil)
    end
end

function AimPoseController.SetPoseDrivenExternally(value: boolean)
    poseDrivenExternally = value == true
end

function AimPoseController.StepAfterExternalPose(deltaTime: number)
    if poseDrivenExternally then
        stepPose(deltaTime)
        -- Composer's PreSimulation connection is intentionally registered first.
        -- Skip the controller's own callback later in this same frame, including
        -- the exit frame where the composer may release external ownership.
        skipOwnStepOnce = true
    end
end

local function applyPose(deltaTime: number)
    if skipOwnStepOnce then
        skipOwnStepOnce = false
        return
    end
    if not poseDrivenExternally then
        stepPose(deltaTime)
    end
end

function AimPoseController.GetAimPosition(): Vector3?
    local camera = Workspace.CurrentCamera
    if not camera then
        return nil
    end

    -- One center-screen reticle owns both attack intent and presentation.
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
    -- duration is the COMPLETE attack interval. The aim response controls how
    -- quickly we reach the angle; it is not a timer that releases the pose early.
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
