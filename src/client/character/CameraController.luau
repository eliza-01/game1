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
local UiInputGuard = require(script.Parent.Parent:WaitForChild("UiInputGuard"))

local CameraController = {}

local localPlayer = Players.LocalPlayer
local started = false
local character: Model? = nil
local root: BasePart? = nil
local rotating = false
local targetYaw = 0
local cameraSettings = GameOptions.CameraSettings()
local targetPitch = math.rad(cameraSettings.pitchDegrees)
local renderedYaw = 0
local renderedPitch = targetPitch
local distance = cameraSettings.distance
local discardNextMouseDelta = false
local touchLookAxis = Vector2.zero

local raycastParameters = RaycastParams.new()
raycastParameters.FilterType = Enum.RaycastFilterType.Exclude
raycastParameters.IgnoreWater = false

local function setCharacter(newCharacter: Model)
	character = newCharacter
	root = nil

	local newRoot = newCharacter:WaitForChild("RootCollider", 10)
	if newRoot and newRoot:IsA("BasePart") then
		root = newRoot
		local look = newRoot.CFrame.LookVector
		targetYaw = math.atan2(-look.X, -look.Z)
		renderedYaw = targetYaw
		renderedPitch = targetPitch
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

local function updateCameraInput(deltaTime: number)
	-- Continuous touch thumbstick (radians/sec) shares the desktop camera's target.
	if touchLookAxis.Magnitude > 0.001 then
		targetYaw -= touchLookAxis.X * CharacterConfig.CameraTouchRotationSpeed * deltaTime
		targetPitch = math.clamp(
			targetPitch + touchLookAxis.Y * CharacterConfig.CameraTouchRotationSpeed * deltaTime,
			CharacterConfig.CameraMinPitch,
			CharacterConfig.CameraMaxPitch
		)
	end
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

	targetYaw -= mouseDelta.X * CharacterConfig.CameraMouseSensitivity
	targetPitch = math.clamp(
		targetPitch - mouseDelta.Y * CharacterConfig.CameraMouseSensitivity,
		CharacterConfig.CameraMinPitch,
		CharacterConfig.CameraMaxPitch
	)
end

local function updateCamera(deltaTime: number)
	local currentRoot = root
	if not currentRoot or not currentRoot.Parent then
		return
	end

	local camera = Workspace.CurrentCamera
	if not camera then
		return
	end

	camera.CameraType = Enum.CameraType.Scriptable
	camera.FieldOfView = CharacterConfig.CameraFieldOfView

	-- Mouse deltas are quantized input samples. Keep the authoritative target angles
	-- exact, but render toward them with a frame-rate-independent exponential response.
	-- This removes the visible one-pixel/one-packet stepping without smoothing the
	-- character follow position itself.
	local response = CharacterConfig.CameraRotationResponse
	local blend = 1 - math.exp(-response * math.max(0, deltaTime))
	renderedYaw += (targetYaw - renderedYaw) * blend
	renderedPitch += (targetPitch - renderedPitch) * blend

	-- Follow the transform Roblox actually renders for the physics root.
	-- Reading .Position here samples the simulation transform and can make the
	-- whole world appear to stutter when render FPS is higher than physics FPS.
	local renderedRootCFrame = currentRoot:GetRenderCFrame()
	local target = renderedRootCFrame.Position + Vector3.new(0, cameraSettings.targetHeight, 0)
	local rotation = CFrame.Angles(0, renderedYaw, 0) * CFrame.Angles(renderedPitch, 0, 0)
	-- Translate the camera frame in its local screen plane; the player appears
    -- at the chosen normalized on-screen position without changing root movement.
    local viewport = camera.ViewportSize
    local aspect = if viewport.Y > 1 then viewport.X / viewport.Y else 1
    local halfHeight = distance * math.tan(math.rad(camera.FieldOfView) * 0.5)
    local halfWidth = halfHeight * aspect
    local screenShift = rotation.RightVector * ((0.5 - cameraSettings.characterX) * 2 * halfWidth)
        + rotation.UpVector * ((cameraSettings.characterY - 0.5) * 2 * halfHeight)
    target += screenShift
    local desiredPosition = target + rotation:VectorToWorldSpace(Vector3.new(0, 0, distance))
	local castDirection = desiredPosition - target

	local cameraPosition = desiredPosition
	local result = Workspace:Raycast(target, castDirection, raycastParameters)
	if result then
		cameraPosition = result.Position + result.Normal * CharacterConfig.CameraCollisionPadding
	end

	camera.CFrame = CFrame.lookAt(cameraPosition, target, Vector3.yAxis)
end

local CAMERA_LIMITS = {
    targetHeight = {0, 12}, distance = {4, 18}, pitchDegrees = {-65, 60},
    characterX = {0.2, 0.8}, characterY = {0.2, 0.8},
    cursorX = {0.1, 0.9}, cursorY = {0.1, 0.9},
}

function CameraController.GetSettings(): {[string]: number}
    return table.clone(cameraSettings)
end

function CameraController.ApplyDebug(settings: {[string]: number}): boolean
    if not RunService:IsStudio() then return false end
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
        renderedPitch = targetPitch
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

function CameraController.GetAimRay(): (Vector3?, Vector3?)
    local camera = Workspace.CurrentCamera
    if not camera then return nil, nil end
    local v = camera.ViewportSize
    local ray = camera:ViewportPointToRay(v.X * cameraSettings.cursorX, v.Y * cameraSettings.cursorY)
    if ray.Direction.Magnitude <= 1e-6 then return nil, nil end
    return ray.Origin, ray.Direction.Unit
end

function CameraController.SetTouchLookAxis(axis: Vector2)
	local magnitude = axis.Magnitude
	touchLookAxis = if magnitude > 1 then axis.Unit else axis
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
