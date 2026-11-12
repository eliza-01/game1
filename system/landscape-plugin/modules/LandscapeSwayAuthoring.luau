-- Editor ownership: static visual attachments and an invisible query hit target.
-- Cleanup is a one-time conversion when applying an older physical placement.
local Authoring = {}
local TARGET = "LandscapeSwayTarget"
local GENERATED = "Game1LandscapePhysics"

local function updateTarget(model: Model, config)
    local existing = model:FindFirstChild(TARGET)
    if existing then
        if not existing:IsA("BasePart") or existing:GetAttribute("Game1LandscapeSwayTarget") ~= true then
            error(TARGET .. " is reserved for the editor")
        end
        existing:Destroy()
    end
    if not (config.tetherEnabled and config.swayEnabled) then return end

    local pivot = model:GetPivot()
    local low, high = Vector3.new(math.huge, math.huge, math.huge), Vector3.new(-math.huge, -math.huge, -math.huge)
    local found = false
    for _, part in ipairs(model:GetDescendants()) do
        if part:IsA("MeshPart") and part.Name ~= "rig_carrier"
            and part:GetAttribute("Game1LandscapeAttachment") ~= true
            and part:GetAttribute("Game1DecoPhysicsOnly") ~= true
            and part.Name:lower():sub(1, 4) ~= "col_" then
            local relative = pivot:ToObjectSpace(part.CFrame)
            local half = part.Size * 0.5
            for _, x in ipairs({-1, 1}) do
                for _, y in ipairs({-1, 1}) do
                    for _, z in ipairs({-1, 1}) do
                        local point = relative:PointToWorldSpace(Vector3.new(x * half.X, y * half.Y, z * half.Z))
                        low = Vector3.new(math.min(low.X, point.X), math.min(low.Y, point.Y), math.min(low.Z, point.Z))
                        high = Vector3.new(math.max(high.X, point.X), math.max(high.Y, point.Y), math.max(high.Z, point.Z))
                    end
                end
            end
            found = true
        end
    end
    if not found then error("Покачивание требует видимый MeshPart") end
    local size = high - low
    if size.Magnitude > 300 then error("Слишком большой ассет для sway-hitbox") end
    local part = Instance.new("Part")
    part.Name = TARGET
    part:SetAttribute("Game1LandscapeSwayTarget", true)
    part.Size = Vector3.new(math.max(0.12, size.X), math.max(0.12, size.Y), math.max(0.12, size.Z))
    part.CFrame = pivot * CFrame.new((high + low) * 0.5)
    part.Transparency = 1
    part.CanCollide = false
    part.CanTouch = false
    part.CanQuery = true
    part.CastShadow = false
    part.Anchored = true
    part.Parent = model
end

function Authoring.Sync(model: Model, config)
    -- Remove native constraints created by M294-M299. This module never adds any.
    for _, instance in ipairs(model:GetDescendants()) do
        if instance:GetAttribute(GENERATED) == true then instance:Destroy() end
    end
    for _, part in ipairs(model:GetDescendants()) do
        if part:IsA("BasePart") then
            local collide = part:GetAttribute("Game1LandscapeOriginalCanCollide")
            local query = part:GetAttribute("Game1LandscapeOriginalCanQuery")
            if typeof(collide) == "boolean" and typeof(query) == "boolean" then
                if collide then
                    part.CanQuery = true
                    part.CanCollide = true
                else
                    part.CanCollide = false
                    part.CanQuery = query
                end
                part:SetAttribute("Game1LandscapeOriginalCanCollide", nil)
                part:SetAttribute("Game1LandscapeOriginalCanQuery", nil)
            end
            local massless = part:GetAttribute("Game1LandscapeOriginalMassless")
            if typeof(massless) == "boolean" then
                part.Massless = massless
                part:SetAttribute("Game1LandscapeOriginalMassless", nil)
            end
            part.Anchored = true
        end
    end
    updateTarget(model, config)
    model:SetAttribute("LandscapeSwayEnabled", config.tetherEnabled and config.swayEnabled)
    model:SetAttribute("LandscapeTetherPhysicsEnabled", nil)
end

return table.freeze(Authoring)
