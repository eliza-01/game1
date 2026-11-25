--!strict
-- Character Creation coordination: authoritative server assembly, local previews,
-- right-side editor, one shared camera controller. No gameplay body/armor editing.
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local GameOptions = require(Shared:WaitForChild("GameOptions"))
local CharacterRegistry = require(Shared:WaitForChild("character"):WaitForChild("CharacterRegistry"))
local SelectionScene = require(Shared:WaitForChild("character"):WaitForChild("CharacterSelectionScene"))
local EyeColors = require(Shared:WaitForChild("character"):WaitForChild("CharacterCreationEyeColors"))
local Catalog = require(Shared:WaitForChild("character"):WaitForChild("CharacterCreationAppearanceRegistry"))
local Language = require(script.Parent.Parent:WaitForChild("localization"):WaitForChild("LanguageState"))
local CameraController = require(script.Parent:WaitForChild("CameraController"))
local Preview = require(script.Parent:WaitForChild("CharacterCreationPreviewController"))
local Editor = require(script.Parent:WaitForChild("CharacterCreationAppearanceView"))
local Panel = require(script.Parent:WaitForChild("CharacterCreationPanel"))
local Controller = {}
local started = false

local function archetype(id: string): any?
    for _, row in ipairs(CharacterRegistry.archetypes or {}) do
        if row.id == id then return row end
    end
    return nil
end

local function defaults(id: string): any
    local row = archetype(id)
    local parts = (row and row.assembly and row.assembly.parts) or {}
    local options = (Catalog.archetypes or {})[id] or {}
    local selected = {materials = {hair = (parts.hair or {}).material or "Plastic",
        eyes = (parts.eye_l or {}).material or "Plastic"},
        colors = {hair = table.clone((parts.hair or {}).colors or {}),
        eyes = EyeColors.Defaults(parts), eyebrows = (parts.eyebrow_l or {}).color or "#000000"}}
    for _, group in ipairs({"hair", "head", "eyes", "eyebrows"}) do
        local part = if group == "eyes" then "eye_l" elseif group == "eyebrows" then "eyebrow_l" else group
        local value = (parts[part] or {}).id or ""
        if group == "eyes" or group == "eyebrows" then value = string.gsub(value, "_[lr]$", "") end
        selected[group] = value
        if selected[group] == "" and options[group] and options[group][1] then
            selected[group] = options[group][1].id
        end
    end
    local allowed = GameOptions.CharacterCreationSettings().materialChoices or {}
    for _, group in ipairs({"hair", "eyes"}) do
        if not table.find(allowed[group] or {"Plastic"}, selected.materials[group]) then
            selected.materials[group] = "Plastic"
        end
    end
    return selected
end

function Controller.Start()
    if started then return end
    started = true
    local player = Players.LocalPlayer
    local settings = GameOptions.CharacterCreationSettings()
    if settings.enabled ~= true then return end
    local gui = Instance.new("ScreenGui")
    gui.Name = "Game1CharacterCreation"
    gui.DisplayOrder = 240
    gui.IgnoreGuiInset = false
    gui.ResetOnSpawn = false
    gui.Enabled = true
    local playerGui = player:WaitForChild("PlayerGui")
    playerGui:SetAttribute("Game1CharacterSceneInputBlocked", true)
    gui.Parent = playerGui
    local curtain = Instance.new("Frame")
    curtain.Name = "SceneTransition"
    curtain.Size = UDim2.fromScale(1, 1)
    curtain.BackgroundColor3 = Color3.fromRGB(12, 17, 21)
    curtain.BorderSizePixel = 0
    curtain.Active = true
    curtain.ZIndex = 1
    curtain.Parent = gui
    local curtainTween: Tween? = nil
    local function cover(opaque: boolean)
        if curtainTween then curtainTween:Cancel(); curtainTween = nil end
        if opaque then
            curtain.BackgroundTransparency = 0
        else
            curtainTween = TweenService:Create(curtain, TweenInfo.new(0.24), {BackgroundTransparency = 1})
            curtainTween:Play()
        end
    end
    -- All presentation geometry is owned by the responsive panel module.
    local controls = Panel.Create(gui, settings)
    local title = controls.title
    local subtitle = controls.subtitle
    local editor = controls.editor
    local Palette = require(script.Parent:WaitForChild("CharacterCreationColorPalette"))
    local palette = Palette.new(controls.panel)
    local selected: string? = nil
    local stage = "loading"
    local lastStage = ""
    local pending = false
    local choices: {[string]: any} = {human_male = defaults("human_male"), human_female = defaults("human_female")}
    local eyeLocks: {[string]: boolean} = {
        human_male = choices.human_male.colors.eyes.l == choices.human_male.colors.eyes.r,
        human_female = choices.human_female.colors.eyes.l == choices.human_female.colors.eyes.r,
    }
    local revisions: {[string]: number} = {human_male = 0, human_female = 0}
    local currentPreview: any? = nil
    local previewRequestBusy = false
    local epoch = 0
    local ready: {[string]: boolean} = {}
    local previewError: {[string]: boolean} = {}
    local readFailed = false
    local sceneReady = false
    local leaving = false
    local activeScene: boolean? = nil
    local selectionAnchors: SelectionScene.Anchors? = nil
    local function remoteFor(name: string): RemoteFunction?
        local remotes = ReplicatedStorage:WaitForChild("Game1Remotes", 15)
        local item = remotes and remotes:WaitForChild(name, 15)
        return if item and item:IsA("RemoteFunction") then item else nil
    end
    local activeTab: string? = nil
    local submitting = false
    local male = controls.male :: TextButton
    local female = controls.female :: TextButton
    local enter = controls.enter :: TextButton
    local status = controls.status :: TextLabel

    local function showStage(snap: boolean?)
        if stage == "selection" then
            return CameraController.ShowCharacterSelectionView(selected, if snap then 0 else settings.transitionSeconds, selectionAnchors)
        end
        local face = activeTab ~= nil
        local name = if not selected then "SelectionOverview"
            else if selected == "human_male" then (if face then "MaleFace" else "MaleFullBody")
            else (if face then "FemaleFace" else "FemaleFullBody")
        local seconds = if face then settings.faceTransitionSeconds else settings.transitionSeconds
        if not CameraController.ShowCreationView(name, if snap then 0 else seconds) then
            warn("[game1][character-creation] camera view unavailable: " .. name)
            return false
        end
        return true
    end

    local refresh: () -> ()
    local function requestPreview(id: string)
        local current = choices[id]
        ready[id] = false
        previewError[id] = nil
        refresh()
        revisions[id] = (revisions[id] or 0) + 1
        local version = revisions[id]
        task.spawn(function()
            -- PreviewService permits one in-flight request per player. Serialise
            -- Male/Female on first load and rapid hairstyle changes instead of
            -- racing RemoteFunction calls into preview_busy.
            while previewRequestBusy do
                if not gui.Enabled or revisions[id] ~= version then return end
                task.wait(0.04)
            end
            if not gui.Enabled or revisions[id] ~= version then return end
            previewRequestBusy = true
            local previewRemote = remoteFor("CharacterCreationPreview")
            if not gui.Enabled or revisions[id] ~= version then previewRequestBusy = false; return end
            local ok, response = false, nil
            if previewRemote then ok, response = pcall(previewRemote.InvokeServer, previewRemote, id, current) end
            previewRequestBusy = false
            if not gui.Enabled or revisions[id] ~= version then return end
            if not ok or type(response) ~= "table" or response.ok ~= true then
                local reason = if ok and type(response) == "table" then response.error else "network"
                warn("[game1][character-creation] preview failed: " .. tostring(reason))
                previewError[id] = true
                refresh()
                return
            end
            if not currentPreview then return end
            local preview = currentPreview
            local function isCurrent(): boolean
                return gui.Enabled and revisions[id] == version and currentPreview == preview and not leaving
            end
            if stage == "selection" then
                -- The server declares whether the optional scene exists. A
                -- temporarily unstreamed scene must not choose a different camera.
                local deadline = os.clock() + 10
                while isCurrent() do
                    local expected = player:GetAttribute("Game1CharacterSelectionScene")
                    if expected == false then selectionAnchors = nil; break end
                    if expected == true then
                        selectionAnchors = SelectionScene.Resolve()
                        if selectionAnchors then break end
                    end
                    if os.clock() >= deadline then
                        previewError[id] = true
                        warn("[game1][character-creation] selection scene not replicated")
                        refresh()
                        return
                    end
                    task.wait(0.1)
                end
                if not isCurrent() then return end
            end
            local called, created = pcall(preview.Set, preview, id, response.template, choices[id], stage, isCurrent, selectionAnchors)
            if not isCurrent() then return end
            ready[id] = called and created == true
            previewError[id] = not ready[id]
            if not ready[id] then warn("[game1][character-creation] preview placement failed: " .. tostring(created)) end
            if ready[id] and not sceneReady then
                sceneReady = showStage(true) == true
                if sceneReady then cover(false) else ready[id] = false; previewError[id] = true end
            end
            refresh()
        end)
    end

    local function pick(group: string, id: string)
        if stage ~= "creation" or not selected or pending or leaving then return end
        local values = choices[selected]
        if values[group] == id then return end
        values[group] = id
        if group == "hair" then
            -- Reset channels on hairstyle changes; extras may differ across styles.
            values.colors.hair = {}
        end
        refresh()
        requestPreview(selected)
    end
    local function paint(group: string, value: string, channel: string?)
        if stage ~= "creation" or not selected or pending or leaving then return end
        local values = choices[selected]
        if group == "eyes" and channel and eyeLocks[selected] then
            values.colors[group]["l"] = value
            values.colors[group]["r"] = value
        elseif channel then values.colors[group][channel] = value
        else values.colors[group] = value end
        refresh()
        if currentPreview then currentPreview:Colors(selected, values.colors) end
    end
    local function material(group: string, value: string)
        if stage ~= "creation" or not selected or pending or leaving then return end
        local allowed = (settings.materialChoices or {})[group] or {}
        if not table.find(allowed, value) then return end
        choices[selected].materials[group] = value
        refresh()
        if currentPreview then currentPreview:Materials(selected, choices[selected].materials) end
    end
    local function customColor(group: string, channel: string?, value: string?)
        if stage ~= "creation" or not selected or pending or leaving then return end
        local id = selected
        local function preview(hex: string)
            if not id or not currentPreview then return end
            local temporary = table.clone(choices[id].colors)
            if channel then
                temporary[group] = table.clone(temporary[group] or {})
                if group == "eyes" and eyeLocks[id] then
                    temporary[group]["l"] = hex
                    temporary[group]["r"] = hex
                else
                    temporary[group][channel] = hex
                end
            else temporary[group] = hex end
            currentPreview:Colors(id, temporary)
        end
        palette:Open(value, preview, function(hex)
            paint(group, hex, channel)
        end, function()
            if id and currentPreview then currentPreview:Colors(id, choices[id].colors) end
        end)
    end
    refresh = function()
        title.Text = Language.Translate("creation.title")
        subtitle.Text = Language.Translate("creation.subtitle")
        male.Text = Language.Translate("creation.male")
        female.Text = Language.Translate("creation.female")
        enter.Text = Language.Translate(if stage == "creation" then "creation.create" else "creation.enter")
        male.BackgroundColor3 = if selected == "human_male" then Color3.fromRGB(81, 107, 98) else Color3.fromRGB(39, 51, 58)
        female.BackgroundColor3 = if selected == "human_female" then Color3.fromRGB(81, 107, 98) else Color3.fromRGB(39, 51, 58)
        local catalog = if selected then (Catalog.archetypes or {})[selected] else nil
        local visible = {}
        for _, category in ipairs({"hair", "eyebrows", "eyes", "head"}) do
            local entries = (catalog and catalog[category]) or {}
            visible[category] = #entries > 1 or (#entries == 1 and category ~= "head")
        end
        if activeTab and not visible[activeTab] then activeTab = nil end
        Panel.UpdateTabs(controls, stage == "creation" and selected ~= nil and not pending, activeTab, visible)
        local selectedReady = selected ~= nil and ready[selected] == true
        local retry = (selected ~= nil and previewError[selected] == true) or (stage == "selection" and readFailed)
        local busy = pending or leaving
        male.Active = not busy
        female.Active = not busy
        enter.Active = not busy and (retry or (selectedReady and sceneReady))
            and (stage == "creation" or stage == "selection")
        if retry then enter.Text = Language.Translate("creation.retry") end
        if busy then enter.Text = Language.Translate(if stage == "selection" and selected then "creation.entering_world" else if stage == "selection" then "creation.loading_profile" else "creation.working") end
        enter.AutoButtonColor = enter.Active
        enter.BackgroundColor3 = if enter.Active then Color3.fromRGB(215, 179, 115) else Color3.fromRGB(55, 65, 69)
        enter.TextColor3 = if enter.Active then Color3.fromRGB(17, 24, 30) else Color3.fromRGB(198, 207, 210)
        if stage == "creation" then
            Editor.Render(editor, if selected then (Catalog.archetypes or {})[selected] else nil,
                if selected then choices[selected] else nil, pick, paint, activeTab,
                settings, material, customColor, if selected then eyeLocks[selected] else true,
                function()
                    if stage ~= "creation" or not selected or pending or leaving then return end
                    eyeLocks[selected] = not eyeLocks[selected]
                    refresh()
                end)
        end
        Panel.SetMode(controls, stage)
        Panel.SetSubmitting(controls, submitting, Language.Translate(
            if leaving or (submitting and stage == "selection") then "creation.entering_world" else "creation.working"))
        if stage == "selection" then
            Panel.SetSelection(controls, if selectedReady then selected else nil)
            title.Text = Language.Translate("creation.selection_title")
            subtitle.Text = Language.Translate(if selectedReady then "creation.selection_subtitle" else "creation.loading_profile")
            if selectedReady and not busy and status.Text == "" and player:GetAttribute("CharacterProfilePersisted") == false then
                status.Text = Language.Translate("creation.session_only")
            end
        elseif stage == "loading" then
            title.Text = Language.Translate("creation.loading_profile")
            subtitle.Text = ""
        elseif stage == "storage_unavailable" then
            title.Text = Language.Translate("creation.selection_title")
            subtitle.Text = Language.Translate("creation.storage_unavailable")
        end
        if retry then status.Text = Language.Translate(if readFailed then "creation.unavailable" else "creation.preview_failed")
        elseif selected and not selectedReady and not pending then status.Text = Language.Translate("creation.loading_profile")
        elseif selectedReady and not pending and status.Text == Language.Translate("creation.loading_profile") then status.Text = "" end
    end

    male.Activated:Connect(function()
        if pending or leaving or stage ~= "creation" then return end
        palette:Close()
        selected = "human_male"; activeTab = nil
        status.Text = ""
        controls.content.CanvasPosition = Vector2.zero
        refresh(); showStage()
    end)
    female.Activated:Connect(function()
        if pending or leaving or stage ~= "creation" then return end
        palette:Close()
        selected = "human_female"; activeTab = nil
        status.Text = ""
        controls.content.CanvasPosition = Vector2.zero
        refresh(); showStage()
    end)
    for _, key in ipairs({"hair", "eyebrows", "eyes", "head"}) do
        local category = key
        controls.tabs[category].Activated:Connect(function()
            if stage ~= "creation" or not selected or pending or leaving then return end
            if not controls.tabs[category].Visible then return end
            palette:Close()
            activeTab = if activeTab == category then nil else category
            controls.content.CanvasPosition = Vector2.zero
            refresh(); showStage()
        end)
    end
    local function readSelection()
        local token = epoch
        readFailed = false
        pending = true
        status.Text = Language.Translate("creation.loading_profile")
        refresh()
        task.spawn(function()
            local ok, response = false, nil
            local readRemote = remoteFor("CharacterCreationRead")
            if epoch ~= token or leaving then return end
            if readRemote then
                ok, response = pcall(readRemote.InvokeServer, readRemote)
            end
            if epoch ~= token or stage ~= "selection" or leaving then return end
            pending = false
            if not ok or type(response) ~= "table" or response.ok ~= true
                or (response.archetype ~= "human_male" and response.archetype ~= "human_female")
                or type(response.appearance) ~= "table" then
                readFailed = true
                refresh()
                return
            end
            selected = response.archetype
            choices[selected] = response.appearance
            if currentPreview then currentPreview:KeepOnly(selected) end
            status.Text = ""
            requestPreview(selected)
        end)
    end
    enter.Activated:Connect(function()
        if pending or leaving or (stage ~= "creation" and stage ~= "selection") then return end
        if stage == "selection" and readFailed then readSelection(); return end
        if not selected then return end
        if previewError[selected] then requestPreview(selected); return end
        if not ready[selected] or not sceneReady then return end
        palette:Close()
        pending = true
        submitting = true
        status.Text = ""
        refresh()
        local chosen = selected
        local requestedStage = stage
        local token = epoch
        task.spawn(function()
            local remote: RemoteFunction? = nil
            local reason = "network"
            local attempts = if requestedStage == "creation" then 4 else 1
            for attempt = 1, attempts do
                if epoch ~= token or leaving then return end
                if not remote then
                    remote = remoteFor(if requestedStage == "creation" then "CharacterCreationSelect" else "CharacterCreationEnter")
                end
                if epoch ~= token or leaving then return end
                local ok, response = false, nil
                if remote then
                    if requestedStage == "creation" then
                        ok, response = pcall(remote.InvokeServer, remote, chosen, choices[chosen])
                    else
                        ok, response = pcall(remote.InvokeServer, remote)
                    end
                end
                if epoch ~= token or leaving then return end
                if ok and type(response) == "table" and response.ok == true then
                    -- Stage attributes, not the RPC response, own the scene transition.
                    local deadline = os.clock() + 8
                    while epoch == token and not leaving and os.clock() < deadline do task.wait(0.1) end
                    if epoch ~= token or leaving then return end
                    reason = "stage_timeout"
                else
                    reason = tostring(if ok and type(response) == "table" then response.error else "network")
                end
                warn("[game1][character-creation] " .. requestedStage .. " attempt " .. attempt .. ": " .. reason)
                if requestedStage ~= "creation" or not ({network = true, request_in_progress = true,
                    request_failed = true, rate_limited = true, assembly_not_ready = true,
                    character_save_failed = true, stage_timeout = true})[reason] then break end
                if attempt < attempts then task.wait(math.min(2 ^ attempt, 5)) end
            end
            if epoch ~= token or leaving then return end
            submitting = false
            status.Text = Language.Translate("creation.unavailable") .. " (" .. reason .. ")"
            pending = false; refresh()
        end)
    end)
    local function sync()
        local nextStage = tostring(player:GetAttribute("CharacterCreationStatus") or "loading")
        -- Attributes can replicate in either order. Stage owns the transition;
        -- pending remains a server gate for existing consumers.
        local active = nextStage ~= "world"
        if active == activeScene and (not active or nextStage == lastStage) then return end
        epoch += 1
        local token = epoch
        activeScene = active
        revisions.human_male += 1
        revisions.human_female += 1
        palette:Close()
        submitting = not active
        Panel.SetSubmitting(controls, submitting, Language.Translate("creation.entering_world"))
        cover(true)
        if currentPreview then currentPreview:Destroy(); currentPreview = nil end
        if active then
            playerGui:SetAttribute("Game1CharacterSceneInputBlocked", true)
            gui.Enabled = true
            controls.panel.Visible = true
            leaving = false
            stage = nextStage
            lastStage = nextStage
            pending = false; activeTab = nil
            selected = nil
            ready = {}; previewError = {}; readFailed = false; sceneReady = false; selectionAnchors = nil
            status.Text = ""
            if stage == "creation" or stage == "selection" then currentPreview = Preview.new(settings) end
            if stage == "creation" then
                choices.human_male = defaults("human_male")
                choices.human_female = defaults("human_female")
                for id, choice in pairs(choices) do
                    eyeLocks[id] = choice.colors.eyes.l == choice.colors.eyes.r
                end
                refresh(); showStage(true)
                requestPreview("human_male")
                requestPreview("human_female")
            elseif stage == "selection" then
                refresh()
                readSelection()
            else
                refresh()
            end
        else
            lastStage = ""
            leaving = true
            controls.panel.Visible = false
            task.spawn(function()
                -- CharacterAdded/RootCollider replication may follow the world
                -- attribute. Keep the curtain until the gameplay camera owns a root.
                local warned = false
                local began = os.clock()
                while epoch == token and not CameraController.ClearCreationView() do
                    if not warned and os.clock() - began > 12 then
                        warned = true
                        warn("[game1][character-creation] waiting for gameplay camera root")
                        -- Keep the world-entry overlay until the camera has a root.
                    end
                    RunService.RenderStepped:Wait()
                end
                if epoch ~= token then return end
                controls.panel.Visible = false
                submitting = false
                Panel.SetSubmitting(controls, false, "")
                cover(false)
                task.wait(0.25)
                if epoch == token then
                    gui.Enabled = false; leaving = false
                    playerGui:SetAttribute("Game1CharacterSceneInputBlocked", false)
                end
            end)
        end
    end
    player:GetAttributeChangedSignal("CharacterCreationPending"):Connect(sync)
    player:GetAttributeChangedSignal("CharacterCreationStatus"):Connect(sync)
    player:GetAttributeChangedSignal("CharacterProfilePersisted"):Connect(refresh)
    Language.Changed:Connect(refresh)
    refresh()
    sync()
end
return Controller
