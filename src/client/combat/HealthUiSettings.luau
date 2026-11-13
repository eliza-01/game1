-- Local visual preview overlay. Saved Options remain immutable and authoritative.
-- The Studio editor may preview mobile settings on desktop, never replicating a
-- gameplay attribute or replacing an authored profile without explicit Save.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local UserInputService = game:GetService("UserInputService")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local GameOptions = require(Shared:WaitForChild("GameOptions"))

local Settings = {}
local changed = Instance.new("BindableEvent")
local previewDevice: string? = nil
local preview: {[string]: any}? = nil
local previewAllMonsters = false

local function clone(value: any): any
    if type(value) ~= "table" then return value end
    local result = {}
    for key, item in pairs(value) do result[key] = clone(item) end
    return result
end

function Settings.RuntimeDevice(): string
    return if UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled then "mobile" else "desktop"
end

function Settings.CurrentDevice(): string
    return previewDevice or Settings.RuntimeDevice()
end

function Settings.Saved(device: string): {[string]: any}
    return clone(GameOptions.HealthUiSettings(device))
end

function Settings.Current(): {[string]: any}
    return if preview then clone(preview) else Settings.Saved(Settings.RuntimeDevice())
end

function Settings.Preview(device: string, settings: {[string]: any})
    if device ~= "desktop" and device ~= "mobile" then return end
    previewDevice = device
    preview = clone(settings)
    changed:Fire()
end

function Settings.IsPreviewing(): boolean
    return preview ~= nil
end

-- Editing HP style must NOT automatically reveal every neutral monster.
-- The debug operator may explicitly enable this while tuning overhead bars.
function Settings.ShowAllMonsters(): boolean
    return preview ~= nil and previewAllMonsters
end

function Settings.SetShowAllMonsters(enabled: boolean)
    previewAllMonsters = enabled == true
    changed:Fire()
end

function Settings.ClearPreview()
    previewDevice = nil
    preview = nil
    previewAllMonsters = false
    changed:Fire()
end

function Settings.Changed(callback: () -> ()): RBXScriptConnection
    return changed.Event:Connect(callback)
end

return table.freeze(Settings)
