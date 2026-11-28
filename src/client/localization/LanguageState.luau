--!strict
-- Client presentation locale. Never makes gameplay decisions or trusts client
-- language data for server action validation. Shared by all gameplay presenters.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Catalog = require(Shared:WaitForChild("localization"):WaitForChild("GameTextCatalog"))
local Contract = require(Shared:WaitForChild("localization"):WaitForChild("LanguageContract"))
local State = {}
local selected = Contract.Normalize(Players.LocalPlayer.LocaleId)
local changed = Instance.new("BindableEvent")
local sourceKeys: {[string]: string} = {}
local originalText: {[Instance]: string} = setmetatable({}, {__mode = "k"}) :: any
local applying: {[Instance]: boolean} = setmetatable({}, {__mode = "k"}) :: any
local started = false

for _, group in pairs(Catalog.groups) do
    for key, row in pairs(group) do
        sourceKeys[row.source] = key
    end
end
State.Changed = changed.Event

function State.Current(): string
    return selected
end

function State.Has(key: string): boolean
    local groupName = string.match(key, "^([a-z]+)%.")
    return groupName ~= nil and Catalog.groups[groupName] ~= nil
        and Catalog.groups[groupName][key] ~= nil
end

function State.Translate(key: string, params: {[string]: any}?): string
    return Contract.Translate(selected, key, params)
end

function State.FromSource(source: string): string
    local key = sourceKeys[source]
    return if key then State.Translate(key) else source
end

function State.SetLocale(locale: string): boolean
    if not Contract.IsSupported(locale) then return false end
    if locale == selected then return true end
    selected = locale
    for item, source in pairs(originalText) do
        if item.Parent and (item:IsA("TextLabel") or item:IsA("TextButton")) then
            applying[item] = true
            item.Text = State.FromSource(source)
            applying[item] = nil
        end
    end
    changed:Fire(locale)
    return true
end

local function watch(item: Instance)
    if not (item:IsA("TextLabel") or item:IsA("TextButton")) then return end
    if item:GetAttribute("Game1ManualLocale") == true then return end
    -- Roblox's auto-localizer must not race the explicit player-selected locale.
    -- The player can choose a language different from their Roblox account.
    -- Otherwise Roblox automatic localization could overwrite our selection.
    item.AutoLocalize = false
    local function update()
        if applying[item] then return end
        local value = item.Text
        if sourceKeys[value] then
            originalText[item] = value
            local translated = State.FromSource(value)
            if translated ~= value then
                applying[item] = true
                item.Text = translated
                applying[item] = nil
            end
        else
            -- A dynamic producer changed the content. Never pin an older key.
            -- Existing localized content is not treated as a new source.
            if originalText[item] and value ~= State.FromSource(originalText[item]) then
                originalText[item] = nil
            end
        end
    end
    item:GetPropertyChangedSignal("Text"):Connect(update)
    update()
end

function State.Start()
    if started then return end
    started = true
    local playerGui = Players.LocalPlayer:WaitForChild("PlayerGui")
    for _, item in ipairs(playerGui:GetDescendants()) do watch(item) end
    playerGui.DescendantAdded:Connect(watch)
end

return table.freeze(State)
