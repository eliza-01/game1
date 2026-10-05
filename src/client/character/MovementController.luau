-- Roblox Studio: StarterPlayer.StarterPlayerScripts.Game1Client.MovementController (ModuleScript)
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

local Game1Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Game1Shared:WaitForChild("character")
local CharacterConfig = require(CharacterShared:WaitForChild("CharacterConfig"))
local CharacterMovementConfig = require(CharacterShared:WaitForChild("CharacterMovementConfig"))

local MovementController = {}

local localPlayer = Players.LocalPlayer
local started = false
local keysDown: { [Enum.KeyCode]: boolean } = {}
local jumpRequested = false
local airLockUntil = 0
local facingLockDirection: Vector3? = nil
local facingLockUntil = 0
local aimFacingActive = false
local aimFacingStartedAt = 0
local aimFacingEndsAt = 0
local aimFacingStartDirection: Vector3? = nil
local aimFacingTargetDirection: Vector3? = nil
local aimFacingMaxResidualYaw = 0
local movementLockUntil = 0
local movementMode = "Run"
local movementDirectionMode = "Forward"
local forcedWalk = false

local character: Model? = nil
local root: BasePart? = nil
local navigationRoot: BasePart? = nil
local controllerManager: ControllerManager? = nil
local groundController: GroundController? = nil
local airController: AirController? = nil
local groundSensor: ControllerPartSensor? = nil

local function clearCharacter()
	character = nil
	root = nil
	navigationRoot = nil
	controllerManager = nil
	groundController = nil
	airController = nil
	groundSensor = nil
	jumpRequested = false
	airLockUntil = 0
	facingLockDirection = nil
	facingLockUntil = 0
	aimFacingActive = false
	aimFacingStartedAt = 0
	aimFacingEndsAt = 0
	aimFacingStartDirection = nil
	aimFacingTargetDirection = nil
	aimFacingMaxResidualYaw = 0
	movementLockUntil = 0
	movementMode = "Run"
	movementDirectionMode = "Forward"
	forcedWalk = false
end

local function bindCharacter(newCharacter: Model)
	clearCharacter()

	local newRoot = newCharacter:WaitForChild("RootCollider", 10)
	local newNavigationRoot = newCharacter:WaitForChild("NavigationRoot", 10)
	local newManager = newCharacter:WaitForChild("ControllerManager", 10)
	if not newRoot or not newRoot:IsA("BasePart") then
		warn("[game1] RootCollider is missing")
		return
	end
	if not newNavigationRoot or not newNavigationRoot:IsA("BasePart") then
		warn("[game1] NavigationRoot is missing")
		return
	end
	if not newManager or not newManager:IsA("ControllerManager") then
		warn("[game1] ControllerManager is missing")
		return
	end

	local newGround = newManager:WaitForChild("GroundController", 10)
	local newAir = newManager:WaitForChild("AirController", 10)
	local newSensorPart = newCharacter:WaitForChild("GroundSensorPart", 10)
	local newSensor = newSensorPart and newSensorPart:WaitForChild("GroundSensor", 10)
	if not newGround or not newGround:IsA("GroundController") then
		warn("[game1] GroundController is missing")
		return
	end
	if not newAir or not newAir:IsA("AirController") then
		warn("[game1] AirController is missing")
		return
	end
	if not newSensor or not newSensor:IsA("ControllerPartSensor") then
		warn("[game1] GroundSensor is missing")
		return
	end

	if newManager.RootPart ~= newNavigationRoot then
		warn("[game1] ControllerManager.RootPart is not NavigationRoot")
		return
	end

	character = newCharacter
	root = newRoot
	navigationRoot = newNavigationRoot
	controllerManager = newManager
	groundController = newGround
	airController = newAir
	groundSensor = newSensor
	movementMode = "Run"
	movementDirectionMode = "Forward"
	newManager.BaseMoveSpeed = CharacterMovementConfig.RobloxSpeed(
		newCharacter:GetAttribute("CharacterArchetype"),
		newCharacter:GetAttribute("RunSpeed"),
		"Run"
	)
	newCharacter:SetAttribute("AnimationMovementMode", movementMode)
	newCharacter:SetAttribute("AnimationMovementDirection", movementDirectionMode)
	newCharacter:SetAttribute("MovementState", "Idle")
	newCharacter:SetAttribute("MovementStateAuthority", "ClientDerivedPresentation")
	newCharacter:GetAttributeChangedSignal("RunSpeed"):Connect(function()
		if character == newCharacter and controllerManager then
			controllerManager.BaseMoveSpeed = CharacterMovementConfig.RobloxSpeed(
				newCharacter:GetAttribute("CharacterArchetype"),
				newCharacter:GetAttribute("RunSpeed"),
				movementMode
			)
		end
	end)

	print("[game1] Custom movement bound")
end

local function inputAxis(): Vector2
	local x = 0
	local y = 0

	if keysDown[CharacterConfig.InputBindings.MoveLeft[1]] or keysDown[CharacterConfig.InputBindings.MoveLeft[2]] then
		x -= 1
	end
	if keysDown[CharacterConfig.InputBindings.MoveRight[1]] or keysDown[CharacterConfig.InputBindings.MoveRight[2]] then
		x += 1
	end
	if keysDown[CharacterConfig.InputBindings.MoveForward[1]] or keysDown[CharacterConfig.InputBindings.MoveForward[2]] then
		y += 1
	end
	if keysDown[CharacterConfig.InputBindings.MoveBackward[1]] or keysDown[CharacterConfig.InputBindings.MoveBackward[2]] then
		y -= 1
	end

	local axis = Vector2.new(x, y)
	if axis.Magnitude > 1 then
		axis = axis.Unit
	end
	return axis
end

local function cameraRelativeDirection(axis: Vector2): Vector3
	if axis.Magnitude <= 0 then
		return Vector3.zero
	end

	local camera = Workspace.CurrentCamera
	if not camera then
		return Vector3.zero
	end

	local look = camera.CFrame.LookVector
	local right = camera.CFrame.RightVector
	local forwardFlat = Vector3.new(look.X, 0, look.Z)
	local rightFlat = Vector3.new(right.X, 0, right.Z)

	if forwardFlat.Magnitude < 0.001 or rightFlat.Magnitude < 0.001 then
		return Vector3.zero
	end

	forwardFlat = forwardFlat.Unit
	rightFlat = rightFlat.Unit

	local direction = forwardFlat * axis.Y + rightFlat * axis.X
	if direction.Magnitude > 1 then
		direction = direction.Unit
	end
	return direction
end

local function isGrounded(): boolean
	return groundSensor ~= nil and groundSensor.SensedPart ~= nil
end

local function walkModifierDown(): boolean
	return UserInputService:IsKeyDown(CharacterConfig.InputBindings.WalkModifier[1])
		or UserInputService:IsKeyDown(CharacterConfig.InputBindings.WalkModifier[2])
end

local function isBackwardAxis(axis: Vector2): boolean
	-- S / Down owns a dedicated backpedal mode. W+S cancel to zero and therefore
	-- do not count as backward movement. While backpedalling, A/D are ignored:
	-- S, S+A and S+D all travel exactly backwards.
	return axis.Y < -0.001
end

local function rightMouseDown(): boolean
	return UserInputService:IsMouseButtonPressed(CharacterConfig.InputBindings.CameraOrbit[1])
end

local function cameraForwardDirection(): Vector3
	local camera = Workspace.CurrentCamera
	if not camera then
		return Vector3.zero
	end

	local look = camera.CFrame.LookVector
	local forwardFlat = Vector3.new(look.X, 0, look.Z)
	if forwardFlat.Magnitude < 0.001 then
		return Vector3.zero
	end
	return forwardFlat.Unit
end

local function backwardRelativeDirection(_axis: Vector2, cameraSteering: boolean): Vector3
	if cameraSteering then
		-- RMB keeps camera-relative steering, but backpedal is constrained to one axis.
		-- A/D never add a lateral component while S is held. Camera yaw still changes
		-- the world-space backward trajectory naturally.
		return cameraRelativeDirection(Vector2.new(0, -1))
	end

	-- Without RMB, preserve classic planted backpedal relative to the character's
	-- CURRENT facing. A/D are intentionally ignored while S is held.
	local currentRoot = root
	if not currentRoot then
		return Vector3.zero
	end

	local look = currentRoot.CFrame.LookVector
	local forwardFlat = Vector3.new(look.X, 0, look.Z)
	if forwardFlat.Magnitude < 0.001 then
		return Vector3.zero
	end

	return -forwardFlat.Unit
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

local function rotateYaw(direction: Vector3, angle: number): Vector3
	return CFrame.fromAxisAngle(Vector3.yAxis, angle):VectorToWorldSpace(direction)
end

local function smoothStep01(value: number): number
	local t = math.clamp(value, 0, 1)
	return t * t * (3 - 2 * t)
end

local function clearAimFacingCompensation()
	aimFacingActive = false
	aimFacingStartedAt = 0
	aimFacingEndsAt = 0
	aimFacingStartDirection = nil
	aimFacingTargetDirection = nil
	aimFacingMaxResidualYaw = 0
end

local function applyAimFacingCompensation(now: number)
	if not aimFacingActive or not navigationRoot or not controllerManager then
		return
	end
	local startDirection = aimFacingStartDirection
	local targetDirection = aimFacingTargetDirection
	if not startDirection or not targetDirection then
		return
	end

	local duration = math.max(0.001, aimFacingEndsAt - aimFacingStartedAt)
	local alpha = smoothStep01((now - aimFacingStartedAt) / duration)
	local delta = signedYaw(startDirection, targetDirection)
	local facing = flatUnit(rotateYaw(startDirection, delta * alpha))
	if not facing then
		return
	end

	-- ControllerManager does not reliably rotate a completely stationary custom
	-- character just from FacingDirection. Rotate the physical NavigationRoot; the
	-- gameplay RootCollider and Visual follow through their welds without changing
	-- their vertical offsets.
	local position = navigationRoot.Position
	navigationRoot.CFrame = CFrame.lookAt(position, position + facing, Vector3.yAxis)
	controllerManager.FacingDirection = facing
end

local function applyMovementMode(walkModifierActive: boolean, backwardActive: boolean)
	-- Backward movement is ALWAYS Walk, regardless of Ctrl. The same Walk_<weapon>
	-- clip is played in reverse by CharacterAnimationController.
	local walkActive = walkModifierActive or backwardActive
	local nextMode = walkActive and "Walk" or "Run"
	local nextDirectionMode = backwardActive and "Backward" or "Forward"
	if controllerManager and character then
		controllerManager.BaseMoveSpeed = CharacterMovementConfig.RobloxSpeed(
			character:GetAttribute("CharacterArchetype"),
			character:GetAttribute("RunSpeed"),
			nextMode
		)
	end
	if character and movementMode ~= nextMode then
		movementMode = nextMode
		character:SetAttribute("AnimationMovementMode", nextMode)
	end
	if character and movementDirectionMode ~= nextDirectionMode then
		movementDirectionMode = nextDirectionMode
		character:SetAttribute("AnimationMovementDirection", nextDirectionMode)
	end
	if character then
		local movingMagnitude = if controllerManager then controllerManager.MovingDirection.Magnitude else 0
		local derivedMovement = if movingMagnitude <= 0.001 then "Idle" else nextMode
		if character:GetAttribute("MovementState") ~= derivedMovement then
			character:SetAttribute("MovementState", derivedMovement)
		end
	end
end

local function performJump()
	if not navigationRoot or not controllerManager or not airController then
		return
	end
	if not isGrounded() then
		return
	end

	controllerManager.ActiveController = airController
	airLockUntil = os.clock() + CharacterConfig.JumpGroundIgnoreTime

	local upwardSpeed = navigationRoot.AssemblyLinearVelocity:Dot(Vector3.yAxis)
	local deltaVelocity = math.max(CharacterConfig.JumpVelocity - upwardSpeed, 0)
	if deltaVelocity > 0 then
		navigationRoot:ApplyImpulse(Vector3.yAxis * navigationRoot.AssemblyMass * deltaVelocity)
	end
end

local function updateMovement()
	if not character or not character.Parent then
		clearCharacter()
		return
	end
	if not root or not navigationRoot or not controllerManager or not groundController or not airController or not groundSensor then
		return
	end

	if character and tostring(character:GetAttribute("LifeState") or "Alive") ~= "Alive" then
		controllerManager.MovingDirection = Vector3.zero
		if character:GetAttribute("MovementState") ~= "Idle" then
			character:SetAttribute("MovementState", "Idle")
		end
		return
	end

	if UserInputService:GetFocusedTextBox() then
		controllerManager.MovingDirection = Vector3.zero
		return
	end

	local now = os.clock()
	local axis = inputAxis()
	local backwardActive = isBackwardAxis(axis)
	local backwardCameraSteering = backwardActive and rightMouseDown()
	applyMovementMode(forcedWalk or walkModifierDown(), backwardActive)
	local movementLocked = now < movementLockUntil
	local moveDirection = Vector3.zero
	if not movementLocked then
		moveDirection = backwardActive and backwardRelativeDirection(axis, backwardCameraSteering) or cameraRelativeDirection(axis)
	end
	controllerManager.MovingDirection = moveDirection
	if aimFacingActive and not movementLocked and moveDirection.Magnitude > 0.001 then
		-- Live movement/camera steering owns whole-character facing immediately.
		clearAimFacingCompensation()
	end
	if movementLocked then
		jumpRequested = false
		-- Stop horizontal carry immediately and keep the attack planted in place.
		-- Preserve vertical velocity so gravity/falling still behaves normally.
		local velocity = navigationRoot.AssemblyLinearVelocity
		navigationRoot.AssemblyLinearVelocity = Vector3.new(0, velocity.Y, 0)
	end

	if facingLockDirection and now < facingLockUntil then
		-- Facing lock is independent from movement lock and can be refreshed every
		-- frame while an attack tracks the center reticle.
		controllerManager.FacingDirection = facingLockDirection
	else
		if facingLockDirection then
			facingLockDirection = nil
			facingLockUntil = 0
		end
		if moveDirection.Magnitude > 0.001 then
			if not backwardActive then
				-- Forward/side movement continues to own facing as before.
				controllerManager.FacingDirection = moveDirection
			elseif backwardCameraSteering then
				-- RMB + S: face with the camera while travelling exactly opposite its forward
				-- direction. A/D are ignored for the trajectory while backpedalling.
				local cameraForward = cameraForwardDirection()
				if cameraForward.Magnitude > 0.001 then
					controllerManager.FacingDirection = cameraForward
				end
			end
			-- Backpedal without RMB intentionally preserves the current facing.
		end
	end

	-- Standing bow compensation is deliberately applied after ordinary facing, so
	-- only the stationary attack path can override the root yaw.
	applyAimFacingCompensation(now)

	if now >= airLockUntil then
		if isGrounded() then
			controllerManager.ActiveController = groundController
		else
			controllerManager.ActiveController = airController
		end
	end

	if jumpRequested then
		jumpRequested = false
		if not movementLocked then
			performJump()
		end
	end
end

function MovementController.IsMoving(): boolean
	if movementLockUntil > os.clock() then
		return false
	end
	return inputAxis().Magnitude > 0.001
end

function MovementController.BeginForcedWalk()
	forcedWalk = true
	if controllerManager and character then
		applyMovementMode(true, false)
	end
end

function MovementController.EndForcedWalk()
	forcedWalk = false
	if controllerManager and character then
		local axis = inputAxis()
		applyMovementMode(walkModifierDown(), isBackwardAxis(axis))
	end
end

function MovementController.LockMovement(duration: number)
	movementLockUntil = math.max(movementLockUntil, os.clock() + math.max(0.05, tonumber(duration) or 0.05))
	jumpRequested = false
	if controllerManager then
		controllerManager.MovingDirection = Vector3.zero
	end
	if navigationRoot then
		local velocity = navigationRoot.AssemblyLinearVelocity
		navigationRoot.AssemblyLinearVelocity = Vector3.new(0, velocity.Y, 0)
	end
end

function MovementController.UnlockMovement()
	movementLockUntil = 0
end

function MovementController.LockFacing(direction: Vector3, duration: number)
	local flat = Vector3.new(direction.X, 0, direction.Z)
	if flat.Magnitude <= 0.001 then
		return
	end
	facingLockDirection = flat.Unit
	facingLockUntil = os.clock() + math.max(0.05, tonumber(duration) or 0.05)
	if controllerManager then
		controllerManager.FacingDirection = facingLockDirection
	end
end

function MovementController.UnlockFacing()
	facingLockDirection = nil
	facingLockUntil = 0
end

function MovementController.BeginAimFacingCompensation(duration: number, maxResidualYaw: number)
	if not root then
		return false
	end
	local startDirection = flatUnit(root.CFrame.LookVector)
	if not startDirection then
		return false
	end
	local now = os.clock()
	aimFacingActive = true
	aimFacingStartedAt = now
	aimFacingEndsAt = now + math.max(0.05, tonumber(duration) or 0.05)
	aimFacingStartDirection = startDirection
	aimFacingTargetDirection = startDirection
	aimFacingMaxResidualYaw = math.max(0, tonumber(maxResidualYaw) or 0)
	return true
end

function MovementController.UpdateAimFacingCompensation(aimDirection: Vector3)
	if not aimFacingActive then
		return false
	end
	local startDirection = aimFacingStartDirection
	local aim = flatUnit(aimDirection)
	if not startDirection or not aim then
		return false
	end

	-- Split the desired yaw exactly once: the torso is allowed to keep up to the
	-- configured limit; RootCollider receives only the overflow. Example: 150° aim
	-- with 70° torso limit => root turns 80° and torso retains the final 70°.
	local fullYaw = signedYaw(startDirection, aim)
	local torsoYaw = math.clamp(fullYaw, -aimFacingMaxResidualYaw, aimFacingMaxResidualYaw)
	local rootYaw = fullYaw - torsoYaw
	aimFacingTargetDirection = flatUnit(rotateYaw(startDirection, rootYaw)) or startDirection
	return true
end

function MovementController.EndAimFacingCompensation()
	clearAimFacingCompensation()
end

function MovementController.IsAimFacingCompensationActive(): boolean
	return aimFacingActive
end

function MovementController.Start()
	if started then
		return
	end
	started = true

	UserInputService.InputBegan:Connect(function(input: InputObject, gameProcessed: boolean)
		if gameProcessed then
			return
		end

		if input.UserInputType == Enum.UserInputType.Keyboard then
			keysDown[input.KeyCode] = true
			if input.KeyCode == CharacterConfig.InputBindings.Jump[1] then
				jumpRequested = true
			end
		end
	end)

	UserInputService.InputEnded:Connect(function(input: InputObject)
		if input.UserInputType == Enum.UserInputType.Keyboard then
			keysDown[input.KeyCode] = nil
		end
	end)

	localPlayer.CharacterAdded:Connect(bindCharacter)
	localPlayer.CharacterRemoving:Connect(function(removingCharacter)
		if removingCharacter == character then
			clearCharacter()
		end
	end)

	if localPlayer.Character then
		task.spawn(bindCharacter, localPlayer.Character)
	end

	RunService.PreSimulation:Connect(updateMovement)
end

return MovementController
