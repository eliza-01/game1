local HitFrontFlash = {}

function HitFrontFlash.Create(parent: Instance, config: any, index: number): any
    local part = Instance.new("Part")
    part.Name = ("HitFrontFlashSlot%02d"):format(index)
    part.Size = Vector3.new(0.05, 0.05, 0.05)
    part.Transparency = 1
    part.Anchored = true
    part.CanCollide = false
    part.CanTouch = false
    part.CanQuery = false
    part.CastShadow = false
    part.Parent = parent

    local light = Instance.new("SpotLight")
    light.Name = "ImpactFrontLight"
    light.Enabled = false
    light.Face = Enum.NormalId.Front
    light.Color = Color3.fromRGB(255, 219, 139)
    light.Brightness = config.FrontFlashBrightness
    light.Range = config.FrontFlashRange
    light.Angle = config.FrontFlashAngle
    light.Shadows = false
    light.Parent = part

    return { part = part, light = light, generation = 0 }
end

function HitFrontFlash.Emit(slot: any, config: any, position: Vector3, sourcePosition: Vector3, cameraCFrame: CFrame, critical: boolean)
    local incoming = sourcePosition - position
    if incoming.Magnitude < 0.01 then
        incoming = cameraCFrame.Position - position
    end
    if incoming.Magnitude < 0.01 then return end

    local lightPosition = position + incoming.Unit * config.FrontFlashOffset
    slot.part.CFrame = CFrame.lookAt(lightPosition, position)
    slot.light.Brightness = config.FrontFlashBrightness * (if critical then config.FrontFlashCriticalMultiplier else 1)
    slot.generation += 1
    local generation = slot.generation
    slot.light.Enabled = true
    task.delay(config.FrontFlashDuration, function()
        if slot.generation == generation and slot.light.Parent then
            slot.light.Enabled = false
        end
    end)
end

return table.freeze(HitFrontFlash)
