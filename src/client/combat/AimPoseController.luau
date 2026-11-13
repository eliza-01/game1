local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local AttackConfig = require(CombatShared:WaitForChild("AttackConfig"))
local AimPitchGeometry = require(CombatShared:WaitForChild("AimPitchGeometry"))
local CameraController = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CameraController"))
local CharacterUpperBodyRig = require(script.Parent.Parent:WaitForChild("character")
    :WaitForChild("animation"):WaitForChild("CharacterUpperBodyRig"))

local AimPoseController = {}

local localPlayer = Players.LocalPlayer
local started = false
local character: Model? = nil
local root: BasePart? = nil
local aimBone: Bone? = nil
local previousProcedural: { [Bone]: CFrame } = {}
local targetPosition: Vector3? = nil
local presentationAimDirection: Vector3? = nil
local activeUntil = 0
local renderedYaw = 0
local renderedPitch = 0
local poseDrivenExternally = false
local skipOwnStepOnce = false

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
    gui:SetAttribute("WorldInputPassthrough", true)

    local dot = Instance.new("Frame")
    dot.Name = "Dot"
    dot.AnchorPoint = Vector2.new(0.5, 0.5)
    local cursor = CameraController.CursorPoint()
    dot.Position = UDim2.fromScale(cursor.X, cursor.Y)
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

local function findAimBone(model: Model): (Bone?, string?)
    local visual = model:FindFirstChild("Visual")
    if not visual or not visual:IsA("Model") then
        return nil, "Visual model is missing"
    end
    return CharacterUpperBodyRig.ResolveBridge(visual)
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
    presentationAimDirection = nil
    activeUntil = 0
    renderedYaw = 0
    renderedPitch = 0
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
    local resolvedBone, resolveError = findAimBone(newCharacter)
    aimBone = resolvedBone
    if not aimBone then
        warn("[game1][aim] no compatible upper-body aim pivot; root facing still works: " .. tostring(resolveError))
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

local function desiredTorsoAngles(now: number): (number, number, boolean)
    local currentRoot = root
    if not currentRoot or not currentRoot.Parent then return 0, 0, false end
    local activeAttack = targetPosition ~= nil and now <= activeUntil
    local target = if activeAttack then targetPosition else nil
    -- Melee retains its attack-start target. During a bow clip the presentation
    -- target follows the camera ray until the final frame; this is independent
    -- of the ONE server-side pre-Release hit snapshot.
    if not target then return 0, 0, false end

    local direction = target - currentRoot.Position
    if direction.Magnitude < 0.01 then return 0, 0, false end
    local forward = flatUnit(currentRoot.CFrame.LookVector)
    local horizontal = flatUnit(direction)
    local yaw = if forward and horizontal then signedYaw(forward, horizontal) else 0
    -- The hit point may be above RootCollider even when the camera is looking
    -- DOWN (especially against a monster at point-blank range). Root-to-hit
    -- pitch would jerk the head upward; presentation pitch follows the actual
    -- reticle ray instead. Nearby downward aim fades toward level, while true
    -- upward aim and long-range vertical shots stay available.
    local pitch = AimPitchGeometry.Resolve(
        presentationAimDirection, direction,
        AttackConfig.CloseAimPitchNeutralStuds, AttackConfig.CloseAimPitchFullStuds
    )
    -- NavigationRoot/pelvis face the walking direction during Bow. The same
    -- world-space spine bridge compensates up to a full lateral strafe; the
    -- stationary character retains the authored 70-degree limit.
    local movingBow = activeAttack and character ~= nil
        and string.lower(tostring(character:GetAttribute("EquippedWeaponType") or "")) == "bow"
        and tostring(character:GetAttribute("MovementState") or "Idle") ~= "Idle"
    local yawLimit = if movingBow then AttackConfig.MovingBowTorsoYawLimit else AttackConfig.TorsoYawLimit
    return math.clamp(yaw, -yawLimit, yawLimit),
        math.clamp(pitch, -AttackConfig.TorsoPitchDownLimit, AttackConfig.TorsoPitchUpLimit), true
end

local function applyWorldAim(bone: Bone, yaw: number, pitch: number)
    local currentRoot = root
    if not currentRoot or (math.abs(yaw) <= 0.00001 and math.abs(pitch) <= 0.00001) then
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
    -- Positive pitch raises the reticle; rotate about the character's current
    -- horizontal right axis *after* applying yaw. Never tilt the root or legs.
    local yawedForward = yawRotation:VectorToWorldSpace(currentRoot.CFrame.LookVector)
    local flatForward = flatUnit(yawedForward)
    local pitchAxis = if flatForward then flatForward:Cross(Vector3.yAxis) else Vector3.xAxis
    local pitchRotation = CFrame.fromAxisAngle(pitchAxis.Unit, pitch)
    local desiredWorld = CFrame.new(position) * (pitchRotation * yawRotation * animatedRotation)

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
    local desiredYaw, desiredPitch, active = desiredTorsoAngles(now)
    local response = math.max(1, AttackConfig.TorsoAimResponse)
    local blend = 1 - math.exp(-response * math.max(0, deltaTime))
    -- Use the shortest arc when the camera crosses the -180/180 boundary.
    local yawDelta = math.atan2(math.sin(desiredYaw - renderedYaw), math.cos(desiredYaw - renderedYaw))
    renderedYaw += yawDelta * blend
    renderedPitch += (desiredPitch - renderedPitch) * blend
    if math.abs(renderedYaw) < 0.0001 and desiredYaw == 0 then renderedYaw = 0 end
    if math.abs(renderedPitch) < 0.0001 and desiredPitch == 0 then renderedPitch = 0 end

    local bone = aimBone
    if bone and bone.Parent then
        applyWorldAim(bone, renderedYaw, renderedPitch)
    end

    if character then
        character:SetAttribute("AimTorsoYawDegrees", math.deg(renderedYaw))
        character:SetAttribute("AimTorsoPitchDegrees", math.deg(renderedPitch))
        character:SetAttribute("AimPoseActive", active)
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

function AimPoseController.GetAimRay(): (Vector3?, Vector3?)
    -- The camera and all targeting share one authoring offset.
    return CameraController.GetAimRay()
end

function AimPoseController.GetAimPosition(): Vector3?
    local origin, direction = AimPoseController.GetAimRay()
    if typeof(origin) ~= "Vector3" or typeof(direction) ~= "Vector3" then
        return nil
    end

    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = character and { character } or {}
    local hit = Workspace:Raycast(origin, direction * AttackConfig.MaxAimDistance, params)
    return if hit then hit.Position else origin + direction * AttackConfig.MaxAimDistance
end

function AimPoseController.BeginAttack(target: Vector3, duration: number)
    if typeof(target) ~= "Vector3" then
        return
    end
    -- Melee holds the attack-start reticle direction, just like its fixed yaw
    -- target. Bow refreshes this direction each frame via UpdateTarget.
    local _, direction = CameraController.GetAimRay()
    presentationAimDirection = if typeof(direction) == "Vector3" and direction.Magnitude > 1e-6
        then direction.Unit else nil
    targetPosition = target
    -- duration is the COMPLETE attack interval. The aim response controls how
    -- quickly we reach the angle; it is not a timer that releases the pose early.
    activeUntil = os.clock() + math.max(0.05, tonumber(duration) or 0.05)
end

function AimPoseController.UpdateTarget(target: Vector3, direction: Vector3?)
    if typeof(target) == "Vector3" and os.clock() <= activeUntil then
        targetPosition = target
        if typeof(direction) == "Vector3" and direction.Magnitude > 1e-6 then
            presentationAimDirection = direction.Unit
        end
    end
end

function AimPoseController.EndAttack()
    targetPosition = nil
    presentationAimDirection = nil
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
