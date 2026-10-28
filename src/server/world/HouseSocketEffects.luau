--!strict
-- Runtime-only visuals. No Model or Image publishing, and no persistent
-- authored assets. Stubs are intentionally primitive Parts until real assets exist.
local Effects = {}

local function parentPart(socket: Attachment): BasePart?
    local instance: Instance? = socket
    while instance do
        if instance:IsA("BasePart") then return instance end
        instance = instance.Parent
    end
    return nil
end

function Effects.CreatePlaceholder(house: Model, socket: Attachment, kind: string): BasePart?
    local owner = parentPart(socket)
    if not owner then return nil end
    local part = Instance.new("Part")
    part.Name = if kind == "padlock" then "Game1PadlockPlaceholder" else "Game1ChestPlaceholder"
    part.Size = if kind == "padlock" then Vector3.new(0.35, 0.45, 0.16) else Vector3.new(2.2, 1.4, 1.3)
    part.Material = Enum.Material.SmoothPlastic
    part.Color = Color3.fromRGB(93, 99, 105)
    part.Transparency = 0.4
    part.Anchored = false
    part.Massless = true
    part.CanCollide = false
    part.CanTouch = false
    part.CanQuery = false
    part.CastShadow = false
    part.CFrame = if socket:IsA("Bone") then socket.TransformedWorldCFrame else socket.WorldCFrame
    part:SetAttribute("Game1SocketPlaceholder", kind)
    part.Parent = house
    local weld = Instance.new("WeldConstraint")
    weld.Part0 = owner
    weld.Part1 = part
    weld.Parent = part
    return part
end

function Effects.StartSmoke(socket: Attachment): ParticleEmitter
    local emitter = Instance.new("ParticleEmitter")
    emitter.Name = "Game1ChimneySmoke"
    emitter.Rate = 12
    emitter.Acceleration = Vector3.new(0, 5, 0)
    emitter.Lifetime = NumberRange.new(2.7, 4.3)
    emitter.Speed = NumberRange.new(2, 4.5)
    emitter.SpreadAngle = Vector2.new(17, 17)
    emitter.Rotation = NumberRange.new(0, 360)
    emitter.RotSpeed = NumberRange.new(-15, 15)
    emitter.Size = NumberSequence.new({
        NumberSequenceKeypoint.new(0, 0.7),
        NumberSequenceKeypoint.new(0.5, 1.9),
        NumberSequenceKeypoint.new(1, 3.1),
    })
    emitter.Transparency = NumberSequence.new({
        NumberSequenceKeypoint.new(0, 0.55),
        NumberSequenceKeypoint.new(0.65, 0.72),
        NumberSequenceKeypoint.new(1, 1),
    })
    emitter.Color = ColorSequence.new(Color3.fromRGB(128, 131, 135), Color3.fromRGB(186, 187, 190))
    emitter.LightEmission = 0
    emitter.Enabled = true
    emitter.Parent = socket
    return emitter
end

return table.freeze(Effects)
