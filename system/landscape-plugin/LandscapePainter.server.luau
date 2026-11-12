-- Standalone Game1 Edit-mode landscape authoring. No DecoManager runtime dependency.
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local HttpService = game:GetService("HttpService")
local Workspace = game:GetService("Workspace")
local ChangeHistoryService = game:GetService("ChangeHistoryService")
local Selection = game:GetService("Selection")

local LandscapeWidget = require(script.Parent.modules.LandscapeWidget)
local LandscapeAssetsWidget = require(script.Parent.modules.LandscapeAssetsWidget)
local BranchPlacement = require(script.Parent.modules.BranchPlacement)
local LandscapeProfiles = require(script.Parent.modules.LandscapeProfiles)
local LandscapeAssetCatalog = require(script.Parent.modules.LandscapeAssetCatalog)
local LandscapeAssetPlacement = require(script.Parent.modules.LandscapeAssetPlacement)

local toolbar = plugin:CreateToolbar("game1 · landscape")
local toggle = toolbar:CreateButton("LandscapePainter", "Landscape / asset placement in Edit mode", "")
toggle.ClickableWhenViewportHidden = true
local info = DockWidgetPluginGuiInfo.new(Enum.InitialDockState.Right,
    false, false, 350, 650, 290, 370)
local widget = plugin:CreateDockWidgetPluginGuiAsync("Game1LandscapePainterV1", info)
widget.Title = "game1 · Landscape Painter"
local mouse = plugin:GetMouse()
local active = nil -- nil | "branch" | "asset"
local ui, assetUI
local branchSaveScheduled = false
local function status(message)
    if ui then ui:SetStatus(message) end
    -- Keep placement errors next to the Start button, not only at the end
    -- of the long scrolling dock.
    if assetUI then assetUI:SetStatus(message) end
end
local branch = BranchPlacement.new(Workspace, ChangeHistoryService, mouse, status)
local profiles = LandscapeProfiles.new(plugin, HttpService)
local catalog = LandscapeAssetCatalog.new()
local assets = LandscapeAssetPlacement.new(Workspace, ChangeHistoryService,
    mouse, Selection, catalog, profiles, status)

local function stop()
    if not active then return end
    -- Clear ownership before Deactivate, which itself fires Deactivation.
    active = nil
    branch:Stop()
    assets:Stop()
    ui:SetActive(false)
    assetUI:SetActive(false)
    plugin:Deactivate()
end

local function start(kind)
    if RunService:IsRunning() then
        status("Доступно только в режиме Edit · останови Play")
        return
    end
    if active == kind then stop(); return end
    if active then stop() end

    -- PluginMouse only receives viewport input from an activated plugin.
    plugin:Activate(true)
    if not plugin:IsActivatedWithExclusiveMouse() then
        status("Studio не передала Landscape Painter управление мышью · выбери инструмент снова")
        return
    end

    -- Own the input session BEFORE the first cursor update. Previously an
    -- error during initial preview prevented active from being assigned,
    -- silently disabling both Move and Button1Down after pressing Start.
    active = kind
    local ok, started = pcall(function()
        if kind == "asset" then return assets:Start() end
        branch:Start()
        return true
    end)
    if not ok or not started then
        stop()
        status(if not ok then "Ошибка запуска Landscape Painter: " .. tostring(started)
            else "Сначала выбери загруженный опубликованный ассет в каталоге")
        if not ok then warn("[Game1LandscapePainter] start: " .. tostring(started)) end
        return
    end
    ui:SetActive(kind == "branch")
    assetUI:SetActive(kind == "asset")
end

local function safe(action)
    local ok, result = pcall(action)
    if not ok then status("Landscape Painter: " .. tostring(result)) end
    return ok, result
end

ui = LandscapeWidget.new(widget, {
    toggleMode = function() start("branch") end,
    settingsChanged = function(diameter, level, color)
        branch:SetSettings(diameter, level, color)
        -- Live preview follows every drag, but persistent Studio settings
        -- are written at most once per 0.35s rather than on each mouse pixel.
        if not branchSaveScheduled then
            branchSaveScheduled = true
            task.delay(0.35, function()
                branchSaveScheduled = false
                plugin:SetSetting("LandscapeThickness", ui.thickness)
                plugin:SetSetting("LandscapeLevel", ui.level)
                plugin:SetSetting("LandscapeColor", ui.color:ToHex())
            end)
        end
    end,
    finish = stop,
    status = status,
})
assetUI = LandscapeAssetsWidget.new(ui.content, {
    toggleAsset = function() start("asset") end,
    refreshCatalog = function()
        safe(function()
            local rows = catalog:Refresh()
            assetUI:SetCatalog(rows)
            status("Каталог: " .. #rows .. " опубликованных Location Assets")
        end)
    end,
    selectAsset = function(row)
        safe(function()
            assets:SelectAsset(row)
            assetUI:SelectAsset(row)
        end)
    end,
    configChanged = function(config)
        safe(function() assets:SetConfiguration(config) end)
    end,
    targetModeChanged = function(mode)
        safe(function()
            assets:SetTargetMode(mode)
            status(if mode == "stem" then "Прицел видит только стебли"
                elseif mode == "surface" then "Прицел видит только поверхности"
                else "Прицел: автоматическое крепление к стеблю или поверхности")
        end)
    end,
    saveProfile = function(name, config)
        safe(function()
            local row = profiles:Create(name, config)
            local rows, activeId = profiles:List()
            assetUI:SetProfiles(rows, activeId)
            assetUI:SelectProfile(row.id)
            status("Профиль сохранён: " .. row.name)
        end)
    end,
    useProfile = function(id, enabled)
        safe(function()
            profiles:Use(id, enabled)
            local rows, activeId = profiles:List()
            assetUI:SetProfiles(rows, activeId)
            assets:UpdateCursor(true)
            status(if enabled then "Use: профиль применяется к каждому новому размещению"
                else "Use выключен · используется текущий поворот")
        end)
    end,
    applyProfile = function(id)
        safe(function()
            local item = profiles:Find(id)
            if not item then error("профиль не найден") end
            assets:ApplyToSelection(item)
        end)
    end,
    removeProfile = function(id)
        safe(function()
            profiles:Remove(id)
            local rows, activeId = profiles:List()
            assetUI:SetProfiles(rows, activeId)
            assets:UpdateCursor(true)
            status("Профиль удалён")
        end)
    end,
    status = status,
})
local savedThickness = plugin:GetSetting("LandscapeThickness")
local savedLevel = plugin:GetSetting("LandscapeLevel")
local savedColor = plugin:GetSetting("LandscapeColor")
if typeof(savedThickness) == "number" and savedThickness >= 0.04 and savedThickness <= 4 then
    ui.thickness = savedThickness
end
if typeof(savedLevel) == "number" and savedLevel >= 0 and savedLevel <= 4 then
    ui.level = math.floor(savedLevel)
end
if typeof(savedColor) == "string" and savedColor:match("^%x%x%x%x%x%x$") then
    ui.color = Color3.fromHex("#" .. savedColor)
end
ui:Refresh()
branch:SetSettings(ui.thickness, ui.level, ui.color)
local savedProfiles, savedActive = profiles:List()
assetUI:SetProfiles(savedProfiles, savedActive)

-- Studio event callbacks are not protected by the UI's safe(action) wrapper.
-- Report failures where they can actually be seen; never silently abandon
-- an active session because a preview or commit callback threw.
local lastInputError = nil
local function handleViewportInput(operation, callback)
    local ok, reason = pcall(callback)
    if ok then
        lastInputError = nil
    else
        local message = "Landscape Painter / " .. operation .. ": " .. tostring(reason)
        if message ~= lastInputError then
            lastInputError = message
            status(message)
            warn("[Game1LandscapePainter] " .. message)
        end
    end
end

mouse.Move:Connect(function()
    if active == "branch" then
        handleViewportInput("cursor", function() branch:UpdateCursor(false) end)
    elseif active == "asset" then
        handleViewportInput("cursor", function() assets:UpdateCursor(false) end)
    end
end)
mouse.Button1Down:Connect(function()
    if active == "branch" then
        handleViewportInput("click", function() branch:Click() end)
    elseif active == "asset" then
        handleViewportInput("click", function() assets:Click() end)
    end
end)
UserInputService.InputBegan:Connect(function(input, processed)
    if not active or processed then return end
    if input.KeyCode == Enum.KeyCode.Return or input.KeyCode == Enum.KeyCode.KeypadEnter
        or input.KeyCode == Enum.KeyCode.Escape then
        stop()
    end
end)
plugin.Deactivation:Connect(function()
    if active then
        stop()
        status("Прицел остановлен Studio: другой инструмент забрал мышь · нажми «Начать» ещё раз")
    end
end)
toggle.Click:Connect(function()
    widget.Enabled = not widget.Enabled
    if not widget.Enabled then stop() end
end)
widget:GetPropertyChangedSignal("Enabled"):Connect(function()
    if not widget.Enabled then stop() end
end)
plugin.Unloading:Connect(function()
    stop()
    branch.preview:Clear()
    assets:Destroy()
end)
