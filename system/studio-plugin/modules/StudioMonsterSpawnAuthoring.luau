-- Studio owns the draft and map gesture. The host owns saved records and projection.
local Authoring = {}

function Authoring.new(services)
    local plugin, runService, http = services.plugin, services.RunService, services.HttpService
    local markers = services.markers
    local info = DockWidgetPluginGuiInfo.new(Enum.InitialDockState.Right, false, false, 360, 590, 310, 330)
    local dock = plugin:CreateDockWidgetPluginGui("Game1MonsterSpawnAuthoring_v1", info)
    dock.Title = "game1 · Monster Spawns"
    local toolbarButton = services.toolbar:CreateButton("Game1MonsterSpawnAuthoring", "Author monster spawn zones in Studio", "", "Monster Spawns")
    toolbarButton.ClickableWhenViewportHidden = true
    local canvas = Instance.new("ScrollingFrame")
    canvas.BackgroundColor3 = Color3.fromRGB(26, 31, 39)
    canvas.BorderSizePixel = 0
    canvas.Size = UDim2.fromScale(1, 1)
    canvas.CanvasSize = UDim2.new()
    canvas.AutomaticCanvasSize = Enum.AutomaticSize.Y
    canvas.ScrollBarThickness = 6
    canvas.Parent = dock
    local layout = Instance.new("UIListLayout")
    layout.Padding = UDim.new(0, 6)
    layout.SortOrder = Enum.SortOrder.LayoutOrder
    layout.Parent = canvas
    local pad = Instance.new("UIPadding")
    pad.PaddingTop = UDim.new(0, 9); pad.PaddingBottom = UDim.new(0, 9)
    pad.PaddingLeft = UDim.new(0, 9); pad.PaddingRight = UDim.new(0, 15)
    pad.Parent = canvas
    local order = 0
    local status = Instance.new("TextLabel")
    status.Size = UDim2.new(1, 0, 0, 52); status.TextWrapped = true; status.BackgroundTransparency = 1
    status.TextColor3 = Color3.fromRGB(187, 219, 211); status.TextSize = 15; status.Font = Enum.Font.SourceSans
    status.Text = "Open Control Center to load Database."
    status.LayoutOrder = 0; status.Parent = canvas
    local content = Instance.new("Frame")
    content.BackgroundTransparency = 1; content.Size = UDim2.new(1, 0, 0, 0)
    content.AutomaticSize = Enum.AutomaticSize.Y; content.LayoutOrder = 1; content.Parent = canvas
    local catalog, draft, group, selected = nil, nil, nil, nil
    local busy = false
    local renderList, renderForm
    local function setStatus(text) status.Text = tostring(text) end
    local function guard()
        assert(not runService:IsRunning(), "Stop Play before editing monster spawn zones")
    end
    local function request(path, payload)
        guard()
        local options = {Url = services.agentBaseUrl .. path, Method = if payload then "POST" else "GET",
            Headers = {["X-Control-Token"] = services.agentToken, ["Content-Type"] = "application/json"}}
        if payload then options.Body = http:JSONEncode(payload) end
        local response = http:RequestAsync(options)
        local result = http:JSONDecode(response.Body)
        if not response.Success then error(result.error or tostring(response.StatusCode)) end
        return result
    end
    local function run(action)
        if busy then return end
        busy = true
        local ok, err = pcall(action)
        busy = false
        if not ok then setStatus(err) end
    end
    local function clear()
        content:ClearAllChildren()
        local list = Instance.new("UIListLayout")
        list.SortOrder = Enum.SortOrder.LayoutOrder; list.Padding = UDim.new(0, 6); list.Parent = content
        order = 0
    end
    local function line(parent, class, text, height)
        local item = Instance.new(class)
        order += 1
        item.LayoutOrder = order; item.Size = UDim2.new(1, 0, 0, height or 30)
        item.BackgroundColor3 = Color3.fromRGB(43, 52, 63); item.BorderSizePixel = 0
        item.Text = text; item.TextColor3 = Color3.fromRGB(231, 238, 243); item.TextSize = 15
        item.Font = Enum.Font.SourceSans; item.Parent = parent
        return item
    end
    local function label(text, height)
        local item = line(content, "TextLabel", text, height or 24)
        item.BackgroundTransparency = 1; item.TextXAlignment = Enum.TextXAlignment.Left; item.TextWrapped = true
        return item
    end
    local function button(text, callback)
        local item = line(content, "TextButton", text, 32)
        item.Activated:Connect(function()
            if runService:IsRunning() then setStatus("Stop Play before editing spawn zones"); return end
            if not busy then callback() end
        end)
        return item
    end
    local function numberField(title, key, step, lo, hi, integer)
        label(title)
        local row = Instance.new("Frame")
        order += 1; row.LayoutOrder = order; row.Size = UDim2.new(1,0,0,30); row.BackgroundTransparency = 1; row.Parent = content
        local minus = line(row, "TextButton", "−", 30); minus.Size = UDim2.fromOffset(36,30)
        local input = line(row, "TextBox", tostring(draft[key]), 30); input.ClearTextOnFocus = false
        input.Size = UDim2.new(1,-84,0,30); input.Position = UDim2.fromOffset(42,0)
        local plus = line(row,"TextButton","+",30); plus.Size = UDim2.fromOffset(36,30); plus.Position = UDim2.new(1,-36,0,0)
        local function set(v)
            if not draft or not input.Parent then return end
            if busy or runService:IsRunning() then input.Text = tostring(draft[key]); return end
            local n = tonumber(v)
            if n and n == n and n ~= math.huge and n ~= -math.huge then
                n = math.clamp(n, lo, hi); if integer then n = math.floor(n) end
                draft[key] = n
            end
            input.Text = tostring(draft[key])
            if draft.position then markers.Draw(draft, true) end
        end
        minus.Activated:Connect(function() set(draft[key]-step) end)
        plus.Activated:Connect(function() set(draft[key]+step) end)
        input.FocusLost:Connect(function() set(input.Text) end)
    end
    local function toggle(title, key)
        local b
        local function caption() return (if draft[key] then "☑  " else "☐  ") .. title end
        b = button(caption(), function() draft[key] = not draft[key]; b.Text = caption() end)
    end
    local function cancelDraft()
        if draft then markers.ClearPreview(draft.spawnId) end
        draft, group, selected = nil, nil, nil
    end
    local function here(record) return tonumber(record.placeId) == game.PlaceId end
    local function refresh(restore)
        catalog = request("/api/monster-spawns/catalog")
        if restore then
            local records = {}
            for _, record in ipairs(catalog.records) do if here(record) then table.insert(records, record) end end
            markers.Restore(records)
        end
        setStatus("Database loaded · " .. #catalog.species .. " identities")
    end
    local function choose(row, existing)
        selected = row
        local d = catalog.defaults
        draft = if existing then table.clone(existing) else {
            spawnId = "spawn-" .. http:GenerateGUID(false):lower(), placeId = game.PlaceId,
            mapKey = d.mapKey, spawnRadius = d.spawnRadius, maxAlive = d.maxAlive,
            respawnSeconds = d.respawnSeconds, homeRadiusStuds = d.homeRadiusStuds, enabled = d.enabled,
        }
        draft.balanceId = row.id; draft.level = row.level; draft.monsterName = if row.nameEn ~= "" then row.nameEn else row.id
        draft.monsterSlug = ""; draft.aggressive = if existing and type(existing.aggressive) == "boolean" then existing.aggressive else row.aggressive
        draft.deathChase = if existing and type(existing.deathChase) == "boolean" then existing.deathChase else row.deathChase
        draft.aggroRadiusStuds = if existing and existing.aggroRadiusStuds ~= nil then existing.aggroRadiusStuds else row.aggroRadiusStuds
        draft.expectedUpdatedAtUtc = if existing then existing.updatedAtUtc else nil
        renderForm()
    end
    local function levels(species, existing)
        group = species; clear()
        button("‹ Monster list", function() cancelDraft(); renderList() end)
        label((if species.nameEn ~= "" then species.nameEn else species.key) .. " · " .. species.nameRu)
        for _, row in ipairs(species.levels) do
            button(("Lv.%d · %s · %s"):format(row.level, row.type, if row.ready then "READY" else "MODEL PENDING"), function() choose(row, existing) end)
        end
    end
    renderForm = function()
        clear()
        button("‹ Levels / cancel draft", function() cancelDraft(); renderList() end)
        label(draft.monsterName .. " · Lv." .. selected.level .. " · " .. selected.type)
        label(if selected.ready then "Published model and clips ready" else "Planning only · runtime waits for published model and clips", 40)
        local map = line(content, "TextBox", draft.mapKey, 30); map.ClearTextOnFocus = false
        map.PlaceholderText = "Map key"
        map.FocusLost:Connect(function() if draft and not busy and not runService:IsRunning() then draft.mapKey = map.Text end end)
        numberField("Spawn radius · studs", "spawnRadius", 5, 0, 10000, false)
        numberField("Monsters in zone", "maxAlive", 1, 1, 1000, true)
        numberField("Aggro radius · studs", "aggroRadiusStuds", 5, 0, 10000, false)
        toggle("Aggressive", "aggressive")
        button(if draft.deathChase then "Chase: Death Chase (territory)" else "Chase: Home Leash", function() draft.deathChase = not draft.deathChase; renderForm() end)
        if not draft.deathChase then numberField("Home leash · studs", "homeRadiusStuds", 10, 1, 10000, false) end
        numberField("Respawn · sec", "respawnSeconds", 1, 0, 86400, false)
        toggle("Enabled", "enabled")
        button(if draft.position then "Move spawn zone" else "Place spawn zone", function()
            run(function()
                guard(); setStatus("Click a world surface · Esc cancels")
                local point = markers.Place(table.clone(draft), function() return not dock.Enabled or runService:IsRunning() end)
                draft.position, draft.yawDegrees = point.position, point.yawDegrees
                setStatus("Position selected · Apply to save to Database")
                renderForm()
            end)
        end)
        if draft.position then
            label(("Position: %.1f / %.1f / %.1f"):format(draft.position.x,draft.position.y,draft.position.z))
            button("Apply · Save to Database", function()
                run(function()
                    draft.action = "apply"
                    local result = request("/api/monster-spawns/studio-apply", draft)
                    -- HTTP success is authoritative; a marker failure must not lose the saved record.
                    local saved = result.record
                    draft.expectedUpdatedAtUtc = saved.updatedAtUtc
                    markers.Draw(saved, false)
                    cancelDraft(); refresh(false); renderList(); setStatus("Saved · Database updated · Rojo Sync before Play")
                end)
            end)
        end
        if draft.expectedUpdatedAtUtc then
            button("Delete saved zone", function()
                -- Separate confirm action, never delete just by opening a form.
                clear(); label("Delete this spawn zone?", 32)
                button("Confirm delete", function() run(function()
                    request("/api/monster-spawns/studio-apply", {action="delete", spawnId=draft.spawnId,
                        placeId=draft.placeId, expectedUpdatedAtUtc=draft.expectedUpdatedAtUtc})
                    markers.Delete(draft.spawnId); cancelDraft(); refresh(false); renderList(); setStatus("Deleted from Database")
                end) end)
                button("Cancel", renderForm)
            end)
        end
    end
    renderList = function()
        clear()
        button("Refresh Database / restore markers", function() run(function() guard(); cancelDraft(); refresh(true); renderList() end) end)
        if not catalog then return end
        label("MONSTERS · choose species", 28)
        for _, species in ipairs(catalog.species) do
            button((if species.nameEn ~= "" then species.nameEn else species.key) .. " · " .. #species.levels .. " levels", function() levels(species) end)
        end
        label("SAVED ZONES · current Place", 28)
        for _, record in ipairs(catalog.records) do
            if here(record) then
                button((record.monsterName or "Monster") .. " · " .. tostring(record.level or "?") .. " · " .. record.spawnId:sub(-8), function()
                    for _, species in ipairs(catalog.species) do
                        for _, row in ipairs(species.levels) do
                            if row.id == record.balanceId then choose(row, record); return end
                        end
                    end
                    -- Legacy records retain their model/binding until explicitly re-authored.
                    clear(); label("Legacy zone · choose Database identity to edit", 40)
                    for _, species in ipairs(catalog.species) do
                        button(if species.nameEn ~= "" then species.nameEn else species.key, function() levels(species, record) end)
                    end
                    button("Cancel", renderList)
                end)
            end
        end
    end
    local function open()
        if runService:IsRunning() then setStatus("Stop Play before editing spawn zones"); return end
        run(function() cancelDraft(); refresh(true); renderList() end)
    end
    toolbarButton.Click:Connect(function() dock.Enabled = not dock.Enabled end)
    dock:GetPropertyChangedSignal("Enabled"):Connect(function()
        toolbarButton:SetActive(dock.Enabled)
        if dock.Enabled then open() elseif not busy then cancelDraft() end
    end)
    plugin.Unloading:Connect(function() if draft then markers.ClearPreview(draft.spawnId) end end)
    renderList()
    if dock.Enabled then task.defer(open) end
end
return table.freeze(Authoring)
