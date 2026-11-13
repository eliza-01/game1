-- Roblox Studio: StarterPlayer.StarterPlayerScripts.Game1Client.CameraController (ModuleScript)
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

local Game1Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Game1Shared:WaitForChild("character")
local CharacterConfig = require(CharacterShared:WaitForChild("CharacterConfig"))
local GameOptions = require(Game1Shared:WaitForChild("GameOptions"))
local PublishedDebugAccess = require(Game1Shared:WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local UiInputGuard = require(script.Parent.Parent:WaitForChild("UiInputGuard"))
local AutoAimTargeting = require(script.Parent:WaitForChild("MobileAutoAimTargeting"))

local CameraController = {}

local localPlayer = Players.LocalPlayer
local started = false
local character: Model? = nil
local root: BasePart? = nil
local rotating = false
local targetYaw = 0
local cameraSettings = GameOptions.CameraSettings()
local targetPitch = math.rad(cameraSettings.pitchDegrees)
local distance = cameraSettings.distance
local discardNextMouseDelta = false
local autoAimMonster: Model? = nil
local autoAimBone: Bone? = nil
local autoAimNeedsSnap = false
local autoAimChanged = Instance.new("BindableEvent")

local raycastParameters = RaycastParams.new()
raycastParameters.FilterType = Enum.RaycastFilterType.Exclude
raycastParameters.IgnoreWater = false

local function clearAutoAim()
    if autoAimMonster then
        autoAimMonster = nil
        autoAimBone = nil
        autoAimNeedsSnap = false
        autoAimChanged:Fire(nil)
    end
end


local function setCharacter(newCharacter: Model)
    clearAutoAim()
	character = newCharacter
	root = nil

	local newRoot = newCharacter:WaitForChild("RootCollider", 10)
	if newRoot and newRoot:IsA("BasePart") then
		root = newRoot
		local look = newRoot.CFrame.LookVector
		targetYaw = math.atan2(-look.X, -look.Z)
		raycastParameters.FilterDescendantsInstances = { newCharacter }
	end
end


local function releaseMouse()
	rotating = false
	discardNextMouseDelta = false
	if UserInputService.MouseBehavior == Enum.MouseBehavior.LockCurrentPosition then
		UserInputService.MouseBehavior = Enum.MouseBehavior.Default
	end
end

local function updateCameraInput(_deltaTime: number)
	if not rotating then
		return
	end

	-- Sample mouse motion once per render frame at the dedicated Input priority.
	-- Processing every InputChanged mouse packet can make a scripted camera advance
	-- in uneven chunks when mouse polling rate and render rate do not line up.
	local mouseDelta = UserInputService:GetMouseDelta()
	if discardNextMouseDelta then
		-- LockCurrentPosition can expose a stale/re-centering delta on the first
		-- frame after RMB capture. Consume it without rotating the camera.
		discardNextMouseDelta = false
		return
	end

	if mouseDelta == Vector2.zero then
		return
	end

    clearAutoAim()
	targetYaw -= mouseDelta.X * CharacterConfig.CameraMouseSensitivity
	targetPitch = math.clamp(
		targetPitch - mouseDelta.Y * CharacterConfig.CameraMouseSensitivity,
		CharacterConfig.CameraMinPitch,
		CharacterConfig.CameraMaxPitch
	)
end

local function setCameraOrbit(camera: Camera, currentRoot: BasePart)
    camera.CameraType = Enum.CameraType.Scriptable
    camera.FieldOfView = CharacterConfig.CameraFieldOfView
    local renderedRootCFrame = currentRoot:GetRenderCFrame()
    local target = renderedRootCFrame.Position + Vector3.new(0, cameraSettings.targetHeight, 0)
    local rotation = CFrame.Angles(0, targetYaw, 0) * CFrame.Angles(targetPitch, 0, 0)
    local viewport = camera.ViewportSize
    local aspect = if viewport.Y > 1 then viewport.X / viewport.Y else 1
    local halfHeight = distance * math.tan(math.rad(camera.FieldOfView) * 0.5)
    local halfWidth = halfHeight * aspect
    local screenShift = rotation.RightVector * ((0.5 - cameraSettings.characterX) * 2 * halfWidth)
        + rotation.UpVector * ((cameraSettings.characterY - 0.5) * 2 * halfHeight)
    target += screenShift
    local desiredPosition = target + rotation:VectorToWorldSpace(Vector3.new(0, 0, distance))
    local cameraPosition = desiredPosition
    local result = Workspace:Raycast(target, desiredPosition - target, raycastParameters)
    if result then cameraPosition = result.Position + result.Normal * CharacterConfig.CameraCollisionPadding end
    camera.CFrame = CFrame.lookAt(cameraPosition, target, Vector3.yAxis)
    camera.Focus = CFrame.new(target)
end

local function updateCamera(_deltaTime: number)
    local currentRoot = root
    local camera = Workspace.CurrentCamera
    if not currentRoot or not currentRoot.Parent or not camera then return end

    local focusPoint = if autoAimMonster and autoAimBone
        then AutoAimTargeting.Point(autoAimMonster, autoAimBone) else nil
    if autoAimMonster and not focusPoint then clearAutoAim() end

    if focusPoint then
        local delta = focusPoint - currentRoot.Position
        local radius = math.clamp(tonumber((GameOptions.HealthUiSettings(
            if UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled
            then "mobile" else "desktop").monster or {}).maxDistanceStuds) or 100, 20, 800)
        if delta.Magnitude > radius then
            clearAutoAim()
            focusPoint = nil
        end
    end

    if focusPoint then
        -- The first press snaps towards targets even behind the camera.
        -- Following frames preserve the last solution: only small corrections
        -- are needed as the neck moves, avoiding repeated full camera searches.
        if autoAimNeedsSnap then
            local pivot = currentRoot:GetRenderCFrame().Position + Vector3.new(0, cameraSettings.targetHeight, 0)
            local delta = focusPoint - pivot
            local flat = Vector3.new(delta.X, 0, delta.Z)
            if flat.Magnitude > 0.01 then
                targetYaw = math.atan2(-delta.X, -delta.Z)
                targetPitch = math.clamp(math.atan2(delta.Y, flat.Magnitude),
                    CharacterConfig.CameraMinPitch, CharacterConfig.CameraMaxPitch)
            end
            autoAimNeedsSnap = false
        end
        -- The character/cursor are not necessarily centred. WorldToViewportPoint
        -- accounts for the actual viewport and collision-limited camera CFrame.
        local size = camera.ViewportSize
        local pixelRadians = 2 * math.tan(math.rad(camera.FieldOfView) * 0.5) / math.max(size.Y, 1)
        for _ = 1, 2 do
            setCameraOrbit(camera, currentRoot)
            local projected = camera:WorldToViewportPoint(focusPoint)
            if projected.Z <= 0 then break end
            local errorX = projected.X - size.X * cameraSettings.cursorX
            local errorY = projected.Y - size.Y * cameraSettings.cursorY
            if math.abs(errorX) + math.abs(errorY) < 1.5 then break end
            targetYaw -= math.clamp(errorX * pixelRadians, -0.5, 0.5)
            targetPitch = math.clamp(targetPitch - math.clamp(errorY * pixelRadians, -0.5, 0.5),
                CharacterConfig.CameraMinPitch, CharacterConfig.CameraMaxPitch)
        end
    end
    setCameraOrbit(camera, currentRoot)
end

local CAMERA_LIMITS = {
    targetHeight = {0, 12}, distance = {4, 18}, pitchDegrees = {-65, 60},
    characterX = {0.2, 0.8}, characterY = {0.2, 0.8},
    cursorX = {0.1, 0.9}, cursorY = {0.1, 0.9},
    mobileLookSpeed = {0.25, 4},
}

function CameraController.GetSettings(): {[string]: number}
    return table.clone(cameraSettings)
end

function CameraController.ApplyDebug(settings: {[string]: number}): boolean
    if not PublishedDebugAccess.ClientAllowed() then return false end
    local replacement = table.clone(cameraSettings)
    for key, bounds in CAMERA_LIMITS do
        local value = settings[key]
        if type(value) ~= "number" or value ~= value or value == math.huge or value == -math.huge
            or value < bounds[1] or value > bounds[2] then
            return false
        end
        replacement[key] = value
    end
    local oldPitch = cameraSettings.pitchDegrees
    cameraSettings = replacement
    distance = cameraSettings.distance
    if math.abs(cameraSettings.pitchDegrees - oldPitch) > 1e-6 then
        targetPitch = math.rad(cameraSettings.pitchDegrees)
    end
    local gui = localPlayer:FindFirstChild("PlayerGui")
    local reticle = gui and gui:FindFirstChild("Game1AimReticle")
    local dot = reticle and reticle:FindFirstChild("Dot")
    if dot and dot:IsA("GuiObject") then
        dot.Position = UDim2.fromScale(cameraSettings.cursorX, cameraSettings.cursorY)
    end
    return true
end

function CameraController.CursorPoint(): Vector2
    return Vector2.new(cameraSettings.cursorX, cameraSettings.cursorY)
end

function CameraController.AutoAimTarget(): Model?
    return autoAimMonster
end

function CameraController.AutoAimChanged(callback: (Model?) -> ()): RBXScriptConnection
    return autoAimChanged.Event:Connect(callback)
end

function CameraController.ToggleAutoAim(): boolean
    if autoAimMonster then
        clearAutoAim()
        return false
    end
    if not UserInputService.TouchEnabled or not character or not root then return false end
    local profile = GameOptions.HealthUiSettings(
        if UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled then "mobile" else "desktop")
    local radius = math.clamp(tonumber((profile.monster or {}).maxDistanceStuds) or 100, 20, 800)
    local selected, bone = AutoAimTargeting.Acquire(character, radius)
    if not selected or not bone then return false end
    autoAimMonster, autoAimBone = selected, bone
    autoAimNeedsSnap = true
    autoAimChanged:Fire(selected)
    return true
end

function CameraController.GetAimRay(): (Vector3?, Vector3?)
    local camera = Workspace.CurrentCamera
    if not camera then return nil, nil end
    local v = camera.ViewportSize
    local ray = camera:ViewportPointToRay(v.X * cameraSettings.cursorX, v.Y * cameraSettings.cursorY)
    if ray.Direction.Magnitude <= 1e-6 then return nil, nil end
    return ray.Origin, ray.Direction.Unit
end

-- The touch adapter owns gesture recognition; this controller only consumes deltas.
function CameraController.RotateTouch(delta: Vector2)
    clearAutoAim()
    local sensitivity = CharacterConfig.CameraTouchSensitivity * GameOptions.MobileCameraSpeed()
	targetYaw -= delta.X * sensitivity
	targetPitch = math.clamp(
		targetPitch - delta.Y * sensitivity,
		CharacterConfig.CameraMinPitch,
		CharacterConfig.CameraMaxPitch
	)
end

function CameraController.PinchZoom(previousGap: number, currentGap: number)
	if previousGap <= 5 or currentGap <= 5 then
		return
	end
	-- A widening pinch zooms in. Bound malformed input spikes without smoothing.
	local ratio = math.clamp(previousGap / currentGap, 0.7, 1.4)
	distance = math.clamp(
		distance * ratio,
		CharacterConfig.CameraMinDistance,
		CharacterConfig.CameraMaxDistance
	)
end

function CameraController.Start()
	if started then
		return
	end
	started = true

	UserInputService.InputBegan:Connect(function(input: InputObject, gameProcessed: boolean)
		if input.UserInputType == CharacterConfig.InputBindings.CameraOrbit[1] then
			if UiInputGuard.BlocksWorldInput(input, gameProcessed) then
				return
			end
			rotating = true
			discardNextMouseDelta = true
			UserInputService.MouseBehavior = Enum.MouseBehavior.LockCurrentPosition
		end
	end)

	UserInputService.InputEnded:Connect(function(input: InputObject)
		if input.UserInputType == CharacterConfig.InputBindings.CameraOrbit[1] then
			releaseMouse()
		end
	end)

	UserInputService.InputChanged:Connect(function(input: InputObject, gameProcessed: boolean)
		-- Mouse movement is intentionally NOT handled here. Camera orbit input is
		-- sampled once per render frame in updateCameraInput().
		if input.UserInputType == Enum.UserInputType.MouseWheel then
			if UiInputGuard.BlocksWorldInput(input, gameProcessed) then
				return
			end
			distance = math.clamp(
				distance - input.Position.Z * CharacterConfig.CameraZoomStep,
				CharacterConfig.CameraMinDistance,
				CharacterConfig.CameraMaxDistance
			)
		end
	end)

	UserInputService.WindowFocusReleased:Connect(releaseMouse)

	localPlayer.CharacterAdded:Connect(setCharacter)
	localPlayer.CharacterRemoving:Connect(function(removingCharacter)
		if removingCharacter == character then
			character = nil
			root = nil
            clearAutoAim()
			releaseMouse()
		end
	end)

	if localPlayer.Character then
		task.spawn(setCharacter, localPlayer.Character)
	end

	RunService:BindToRenderStep(
		"game1CameraInput",
		Enum.RenderPriority.Input.Value + 1,
		updateCameraInput
	)

	RunService:BindToRenderStep(
		"game1CustomCamera",
		Enum.RenderPriority.Camera.Value + 1,
		updateCamera
	)
end

return CameraController
