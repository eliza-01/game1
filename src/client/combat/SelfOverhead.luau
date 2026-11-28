-- Dedicated self view, never competes with the MNPC cache or allocation budget.
local Settings = require(script.Parent:WaitForChild("HealthUiSettings"))
local Self = {}
Self.__index = Self
function Self.new(factory)
    return setmetatable({factory=factory}, Self)
end
function Self:Clear()
    if self.view then self.view.Destroy() end
    self.view, self.character, self.anchor = nil, nil, nil
end
function Self:ApplyStyle(style)
    if self.view then self.view.ApplyStyle(style) end
end
function Self:Step(character, gui, style)
    local anchor = character and (character:FindFirstChild("RootCollider") or character:FindFirstChild("HumanoidRootPart") or character:FindFirstChild("NavigationRoot"))
    if not gui or not anchor or not anchor:IsA("BasePart") then self:Clear(); return end
    if self.view and (self.character ~= character or self.anchor ~= anchor or not self.view.IsAttached(gui)) then self:Clear() end
    if not self.view then
        local view = self.factory()
        local ok, err = pcall(view.Bind, gui, character, anchor, style)
        if not ok then view.Destroy(); warn("[Overhead] self Bind failed: " .. tostring(err)); return end
        self.view, self.character, self.anchor = view, character, anchor
    end
    local hp = tonumber(character:GetAttribute("HP")) or 0
    local maxHP = tonumber(character:GetAttribute("MaxHP")) or 0
    self.view.SetVisible(character:GetAttribute("LifeState") == "Alive"
        and (Settings.IsPreviewing() or character:GetAttribute("InCombat") == true or hp < maxHP - 0.001))
end
return table.freeze(Self)
