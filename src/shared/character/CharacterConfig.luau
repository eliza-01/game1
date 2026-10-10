local CharacterConfig = {}
CharacterConfig.DefaultArchetype = "default"
CharacterConfig.RootColliderSize = Vector3.new(2.2, 2.0, 1.4)
-- The non-collidable RootCollider bottom and visual sole share the floor plane.
CharacterConfig.RootGroundClearance = 0
CharacterConfig.RootAnchorOffset = CharacterConfig.RootColliderSize.Y * 0.5 + CharacterConfig.RootGroundClearance
CharacterConfig.NavigationRootSize = Vector3.new(2.0, 2.0, 1.0)
-- Lift the collidable navigation proxy above low steps and seams.
CharacterConfig.NavigationHipHeight = 1.8
CharacterConfig.NavigationCenterOffset = CharacterConfig.NavigationRootSize.Y * 0.5 + CharacterConfig.NavigationHipHeight
-- GroundOffset is clearance BELOW the navigation box, not centre-to-floor.
-- Pair it with the hip height to leave RootCollider and feet at ground level.
CharacterConfig.GroundOffset = CharacterConfig.NavigationHipHeight
CharacterConfig.GroundSearchDistance = CharacterConfig.NavigationCenterOffset + 1.0
CharacterConfig.SpawnClearance = 0
CharacterConfig.VisualGroundClearance = 0
-- RootPart must still have nonzero size when visual ground clearance is zero.
CharacterConfig.VisualRootAnchorSize = Vector3.new(0.35, 0.03, 0.35)
CharacterConfig.TurnSpeed = 12
CharacterConfig.JumpVelocity = 34
CharacterConfig.JumpGroundIgnoreTime = 0.18
CharacterConfig.CameraTargetHeight = 5.5
CharacterConfig.CameraDistance = 10
CharacterConfig.CameraMinDistance = 4
CharacterConfig.CameraMaxDistance = 18
CharacterConfig.CameraPitch = math.rad(-12)
CharacterConfig.CameraMinPitch = math.rad(-65)
CharacterConfig.CameraMaxPitch = math.rad(35)
CharacterConfig.CameraMouseSensitivity = 0.004
CharacterConfig.CameraRotationResponse = 75
CharacterConfig.CameraZoomStep = 1.25
CharacterConfig.CameraCollisionPadding = 0.3
CharacterConfig.CameraFieldOfView = 70
CharacterConfig.InputBindings = table.freeze({
    MoveForward = { Enum.KeyCode.W, Enum.KeyCode.Up },
    MoveBackward = { Enum.KeyCode.S, Enum.KeyCode.Down },
    MoveLeft = { Enum.KeyCode.A, Enum.KeyCode.Left },
    MoveRight = { Enum.KeyCode.D, Enum.KeyCode.Right },
    Jump = { Enum.KeyCode.Space },
    WalkModifier = { Enum.KeyCode.LeftControl, Enum.KeyCode.RightControl },
    CameraOrbit = { Enum.UserInputType.MouseButton2 },
    AttackPrimary = { Enum.UserInputType.MouseButton1 },
})
return table.freeze(CharacterConfig)
