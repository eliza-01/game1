--!strict
-- A viewport-wide presentation layer independent of safe-area controls.
local Layer = {}
function Layer.Create(owner: ScreenGui, name: string, order: number): ScreenGui
    local gui = Instance.new("ScreenGui")
    gui.Name = name
    gui.DisplayOrder = order
    gui.ResetOnSpawn = false
    gui.IgnoreGuiInset = true
    gui.ScreenInsets = Enum.ScreenInsets.None
    gui.ClipToDeviceSafeArea = false
    gui.Enabled = owner.Enabled
    gui.Parent = owner.Parent
    owner:GetPropertyChangedSignal("Enabled"):Connect(function() gui.Enabled = owner.Enabled end)
    owner.Destroying:Connect(function() gui:Destroy() end)
    return gui
end
return table.freeze(Layer)
