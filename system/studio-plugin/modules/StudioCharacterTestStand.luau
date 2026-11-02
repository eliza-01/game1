-- Game1Bridge composition root for the Studio-only character assembly stand.
-- Build -> Place are explicit user actions; this module owns the draft lifetime.
local StudioCharacterStandBuilder = require(script.Parent.StudioCharacterStandBuilder)
local StudioCharacterStandPlacement = require(script.Parent.StudioCharacterStandPlacement)
local StudioCharacterStandWidget = require(script.Parent.StudioCharacterStandWidget)

local TestStand = {}
TestStand.__index = TestStand

function TestStand.new(services: any): any
    local self = setmetatable({
        plugin = services.plugin,
        workspace = services.Workspace,
        runService = services.RunService,
        assetService = services.AssetService,
        selection = services.Selection,
        history = services.ChangeHistoryService,
        mouse = services.plugin:GetMouse(),
        profiles = {},
        selectedIndex = 1,
        draft = nil,
        busy = false,
        placing = false,
        destroyed = false,
        connections = {},
    }, TestStand)
    self.ui = StudioCharacterStandWidget.new(services.plugin)
    self.button = services.toolbar:CreateButton("Game1CharacterStand", "Assemble & place test characters", "", "Character Stand")
    self.button.ClickableWhenViewportHidden = true

    table.insert(self.connections, self.button.Click:Connect(function()
        self.ui.dock.Enabled = not self.ui.dock.Enabled
        if self.ui.dock.Enabled then self:RefreshProfiles() end
    end))
    table.insert(self.connections, self.ui.profile.MouseButton1Click:Connect(function()
        if self.busy or self.placing then return end
        self.selectedIndex = self.selectedIndex % math.max(1, #self.profiles) + 1
        self:SelectProfile()
    end))
    table.insert(self.connections, self.ui.build.MouseButton1Click:Connect(function()
        self:Assemble()
    end))
    table.insert(self.connections, self.ui.place.MouseButton1Click:Connect(function()
        self:BeginPlacement()
    end))
    table.insert(self.connections, self.mouse.Button1Down:Connect(function()
        self:PlaceAtMouse()
    end))
    table.insert(self.connections, services.plugin.Deactivation:Connect(function()
        if self.placing then self:CancelPlacement("Размещение отменено.") end
    end))
    table.insert(self.connections, services.plugin.Unloading:Connect(function()
        self:Destroy()
    end))
    table.insert(self.connections, self.ui.dock:GetPropertyChangedSignal("Enabled"):Connect(function()
        if not self.ui.dock.Enabled and self.placing then self:CancelPlacement("Размещение отменено.") end
    end))
    return self
end

function TestStand:SetStatus(text: string)
    if not self.destroyed then self.ui.status.Text = text end
end

function TestStand:SelectProfile()
    local profile = self.profiles[self.selectedIndex]
    self.ui.profile.Text = if profile then profile.label .. "  ▾" else "Нет опубликованных профилей"
    if self.draft then
        self.draft:Destroy()
        self.draft = nil
    end
    if profile then self:SetStatus("Выбран: " .. profile.id .. ". Нажми «Собрать персонажа».") end
end

function TestStand:RefreshProfiles()
    if self.busy or self.placing then return end
    local old = self.profiles[self.selectedIndex]
    local oldId = old and old.id
    local ok, profiles = pcall(StudioCharacterStandBuilder.Profiles)
    if not ok then
        self:SetStatus("CharacterRegistry: " .. tostring(profiles))
        return
    end
    self.profiles = profiles
    self.selectedIndex = 1
    if oldId then
        for index, profile in ipairs(profiles) do
            if profile.id == oldId then self.selectedIndex = index; break end
        end
    end
    local selected = self.profiles[self.selectedIndex]
    self.ui.profile.Text = if selected then selected.label .. "  ▾" else "Нет опубликованных профилей"
    if self.draft and selected and tostring(self.draft:GetAttribute("Game1AnimationProfileId")) == selected.id then
        self:SetStatus("Собран: " .. selected.id .. ". Нажми «Поставить на поверхность».")
    else
        self:SelectProfile()
    end
end

function TestStand:Assemble()
    if self.destroyed or self.busy or self.placing or self.runService:IsRunning() then
        self:SetStatus("Сборка доступна только в режиме Edit.")
        return
    end
    local profile = self.profiles[self.selectedIndex]
    if not profile then self:SetStatus("Сначала выбери опубликованный профиль."); return end
    self.busy = true
    self.ui.build.Active = false
    self:SetStatus("Загружаю опубликованные Model Assets: " .. profile.id .. "…")
    task.spawn(function()
        local ok, result = xpcall(function()
            return StudioCharacterStandBuilder.Build(self.assetService, profile)
        end, debug.traceback)
        self.busy = false
        self.ui.build.Active = true
        if self.destroyed then
            if ok then result:Destroy() end
            return
        end
        if not ok then
            self:SetStatus("Сборка не удалась: " .. tostring(result))
            warn("[game1][character-stand] assembly failed", result)
            return
        end
        if self.draft then self.draft:Destroy() end
        self.draft = result
        self:SetStatus("Собран: " .. profile.id .. ". Нажми «Поставить», затем кликни по поверхности.")
    end)
end

function TestStand:BeginPlacement()
    if self.destroyed or self.busy or self.runService:IsRunning() or not self.draft then
        self:SetStatus("Сначала собери персонажа в режиме Edit.")
        return
    end
    self.placing = true
    self:SetStatus("Кликни по поверхности в Workspace. Esc отменяет. Можно ставить несколько копий.")
    self.plugin:Activate(true)
end

function TestStand:CancelPlacement(text: string)
    self.placing = false
    if not self.destroyed then self:SetStatus(text) end
end

function TestStand:PlaceAtMouse()
    if not self.placing or self.busy or self.destroyed or self.runService:IsRunning() then return end
    local ray = self.mouse.UnitRay
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    local stands = self.workspace:FindFirstChild("Game1CharacterTestStands")
    params.FilterDescendantsInstances = if stands then {stands} else {}
    local hit = self.workspace:Raycast(ray.Origin, ray.Direction * 2048, params)
    if not hit then
        self:SetStatus("Нет поверхности под курсором. Выбери Part или Terrain.")
        return
    end
    if hit.Normal.Y < 0.6 then
        self:SetStatus("Нужна горизонтальная поверхность (пол или Terrain).")
        return
    end
    local recordingOk, recording = pcall(function()
        return self.history:TryBeginRecording("Place Character Test Stand")
    end)
    if not recordingOk or not recording then
        self:SetStatus("Undo недоступен: завершить другое редактирование и повторить.")
        return
    end
    local ok, model = pcall(StudioCharacterStandPlacement.Place, self.draft, hit.Position, self.workspace)
    local finished, finishError = pcall(function()
        self.history:FinishRecording(recording, if ok then Enum.FinishRecordingOperation.Commit else Enum.FinishRecordingOperation.Cancel)
    end)
    if not finished then warn("[game1][character-stand] undo recording failed", finishError) end
    if not ok then
        self:SetStatus("Размещение не удалось: " .. tostring(model))
        warn("[game1][character-stand] placement failed", model)
        return
    end
    self.placing = false
    self.plugin:Deactivate()
    self.selection:Set({model})
    self:SetStatus(model.Name .. " размещён. В Studio Play подойди к модели и нажми E.")
end

function TestStand:Destroy()
    if self.destroyed then return end
    self.destroyed = true
    self.placing = false
    if self.draft then self.draft:Destroy(); self.draft = nil end
    for _, connection in ipairs(self.connections) do connection:Disconnect() end
end

return table.freeze(TestStand)
