--!strict
-- Single presentation contract shared by world interactions, progress and toasts.
-- Studio previews live only in the local client; saved data comes from GameOptionsRegistry.
local UserInputService = game:GetService("UserInputService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Options = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("GameOptions"))
local Settings = {}
local changed = Instance.new("BindableEvent")
local previewProfile: {[string]: any}? = nil
local previewDevice: string? = nil

local function clone(value: any): any
    if type(value) ~= "table" then return value end
    local result = {}
    for key, entry in pairs(value) do result[key] = clone(entry) end
    return result
end

function Settings.RuntimeDevice(): string
    return if UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled then "mobile" else "desktop"
end

function Settings.ActiveDevice(): string
    return previewDevice or Settings.RuntimeDevice()
end

function Settings.Saved(device: string): {[string]: any}
    return clone(Options.UiPresentationSettings(device))
end

function Settings.Current(): {[string]: any}
    return if previewProfile then previewProfile else Options.UiPresentationSettings(Settings.ActiveDevice())
end

function Settings.Preview(device: string?, profile: {[string]: any}?)
    previewDevice = device
    previewProfile = if profile then clone(profile) else nil
    changed:Fire()
end

Settings.Changed = changed.Event
return table.freeze(Settings)
