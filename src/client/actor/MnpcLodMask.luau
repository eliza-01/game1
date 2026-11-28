-- Cache exact streamed descendants only while a local MNPC is reduced.
local Visibility = require(script.Parent:WaitForChild("MnpcLocalVisibility"))
local Mask = {}
Mask.__index = Mask
local function effect(node)
    return node:IsA("Light") or node:IsA("ParticleEmitter") or node:IsA("Beam")
        or node:IsA("Trail") or node:IsA("Fire") or node:IsA("Smoke") or node:IsA("Sparkles")
        or node:IsA("BillboardGui") or node:IsA("Highlight")
end
function Mask:_add(node)
    if self.items[node] then return end
    if node:IsA("BasePart") then
        self.items[node] = {part = true}
        Visibility.Set(node, self, true)
    elseif effect(node) then
        local entry = {enabled = node.Enabled}
        self.items[node] = entry
        entry.connection = node:GetPropertyChangedSignal("Enabled"):Connect(function()
            if self.items[node] == entry and node.Enabled then
                entry.enabled = true
                node.Enabled = false
            end
        end)
        node.Enabled = false
        if node:IsA("ParticleEmitter") or node:IsA("Trail") then node:Clear() end
    end
end
function Mask:_remove(node)
    local entry = self.items[node]
    if not entry then return end
    self.items[node] = nil
    if entry.part then Visibility.Set(node, self, false)
    else
        entry.connection:Disconnect()
        node.Enabled = entry.enabled or node.Enabled
    end
end
function Mask.new(model)
    local self = setmetatable({items = {}}, Mask)
    self.added = model.DescendantAdded:Connect(function(node) self:_add(node) end)
    self.removing = model.DescendantRemoving:Connect(function(node) self:_remove(node) end)
    for _, node in ipairs(model:GetDescendants()) do self:_add(node) end
    return self
end
function Mask:Destroy()
    self.added:Disconnect()
    self.removing:Disconnect()
    for node in pairs(self.items) do self:_remove(node) end
end
return Mask
