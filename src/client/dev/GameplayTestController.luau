--!strict
-- Studio gameplay laboratory. Every mutation is validated by GameplayTestService.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local RS = game:GetService("ReplicatedStorage")
local TextService = game:GetService("TextService")
local StudioDebugDock = require(script.Parent:WaitForChild("StudioDebugDock"))
local Shared = RS:WaitForChild("Game1Shared")
local Balance = require(Shared:WaitForChild("balance"):WaitForChild("Balance"))
local Critical = require(Shared:WaitForChild("balance"):WaitForChild("CriticalStats"))
local Access = require(Shared:WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local Controller = {}
local started = false
local PANEL_ID = "GP"
local OPEN = "Game1DebugPanelOpen"
local PANEL_WIDTH, PANEL_HEIGHT = 380, 432
local colors = {panel=Color3.fromRGB(24,33,39), control=Color3.fromRGB(44,59,66), text=Color3.fromRGB(240,239,232), muted=Color3.fromRGB(165,180,185), accent=Color3.fromRGB(78,132,110)}

local function rounded(item: GuiObject)
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(0, 7)
    corner.Parent = item
end
local function button(parent: Instance, text: string, size: UDim2): TextButton
    local b = Instance.new("TextButton")
    b.Text = text; b.Size = size; b.BackgroundColor3 = colors.control; b.TextColor3 = colors.text
    b.BorderSizePixel = 0; b.Font = Enum.Font.GothamBold; b.TextSize = 14
    b.LayoutOrder = #parent:GetChildren(); b.Parent = parent; rounded(b)
    return b
end
local function label(parent: Instance, text: string, size: UDim2): TextLabel
    local l = Instance.new("TextLabel")
    l.Text = text; l.Size = size; l.BackgroundTransparency = 1; l.TextColor3 = colors.text
    l.Font = Enum.Font.Gotham; l.TextSize = 13; l.TextXAlignment = Enum.TextXAlignment.Left
    l.TextWrapped = true; l.Parent = parent
    return l
end
-- Rows fill the available panel width; controls inside cells keep their intrinsic size.
local function row(parent: Instance, height: number): Frame
    local f = Instance.new("Frame")
    f.BackgroundTransparency = 1; f.Size = UDim2.new(1, -6, 0, height); f.LayoutOrder = #parent:GetChildren(); f.Parent = parent
    return f
end
local function horizontal(parent: Instance)
    local layout = Instance.new("UIListLayout")
    layout.FillDirection = Enum.FillDirection.Horizontal; layout.Padding = UDim.new(0, 6)
    layout.SortOrder = Enum.SortOrder.LayoutOrder; layout.VerticalAlignment = Enum.VerticalAlignment.Center
    layout.Parent = parent
end
local function cell(parent: Instance, name: string): Frame
    local f = Instance.new("Frame")
    f.Name = name; f.BackgroundTransparency = 1; f.Size = UDim2.new(0.5, -3, 1, 0); f.LayoutOrder = #parent:GetChildren(); f.Parent = parent
    return f
end
local function contentButton(parent: Instance, text: string, height: number): TextButton
    local width = math.ceil(TextService:GetTextSize(text, 14, Enum.Font.GothamBold, Vector2.new(1000, height)).X) + 16
    return button(parent, text, UDim2.fromOffset(width, height))
end
local function picker(parent: Frame, caption: string, read: () -> string, adjust: (number) -> (), reserved: number?)
    local f = Instance.new("Frame")
    f.BackgroundTransparency = 1; f.Size = UDim2.new(1, -(reserved or 0), 1, 0); f.Parent = parent
    local title = label(f, caption, UDim2.new(1, 0, 0, 15)); title.TextColor3 = colors.muted; title.TextSize = 12
    local previous = button(f, "‹", UDim2.fromOffset(22, 30)); previous.Position = UDim2.fromOffset(0, 16)
    local nextButton = button(f, "›", UDim2.fromOffset(22, 30)); nextButton.AnchorPoint = Vector2.new(1, 0); nextButton.Position = UDim2.new(1, 0, 0, 16)
    local current = label(f, "", UDim2.new(1, -48, 0, 30)); current.Position = UDim2.fromOffset(24, 16)
    current.TextXAlignment = Enum.TextXAlignment.Center; current.TextSize = 11; current.TextScaled = true
    local textLimit = Instance.new("UITextSizeConstraint"); textLimit.MinTextSize = 8; textLimit.MaxTextSize = 11; textLimit.Parent = current
    local function refresh() current.Text = read() end
    previous.Activated:Connect(function() adjust(-1); refresh() end)
    nextButton.Activated:Connect(function() adjust(1); refresh() end)
    refresh()
    return refresh
end
local function recoveryField(parent: Frame, caption: string, changed: () -> ()): () -> number?
    local title = label(parent, caption, UDim2.new(1, 0, 0, 15)); title.TextColor3 = colors.muted; title.TextSize = 12
    local check = button(parent, "", UDim2.fromOffset(25, 30)); check.Name = "Enabled"; check.Position = UDim2.fromOffset(0, 16)
    check.AutoButtonColor = false
    local input = Instance.new("TextBox")
    input.Name = "Rate"; input.Text = "0"; input.ClearTextOnFocus = false
    input.Size = UDim2.fromOffset(72, 30); input.Position = UDim2.fromOffset(30, 16)
    input.BackgroundColor3 = colors.control; input.TextColor3 = colors.text; input.BorderSizePixel = 0
    input.Font = Enum.Font.Gotham; input.TextSize = 14; input.Parent = parent; rounded(input)
    local enabled = false
    check.Activated:Connect(function()
        enabled = not enabled
        check.Text = if enabled then "✓" else ""
        check.BackgroundColor3 = if enabled then colors.accent else colors.control
        changed()
    end)
    input.FocusLost:Connect(function() if enabled then changed() end end)
    return function()
        if not enabled then return 0 end
        return tonumber((input.Text:gsub(",", ".")))
    end
end
local function numericField(parent: Frame, caption: string, value: number, changed: () -> ()): () -> number?
    local title = label(parent, caption, UDim2.new(1, 0, 0, 15)); title.TextColor3 = colors.muted; title.TextSize = 12
    local input = Instance.new("TextBox")
    input.Name = "Value"; input.Text = tostring(value); input.ClearTextOnFocus = false
    input.Size = UDim2.fromOffset(72, 30); input.Position = UDim2.fromOffset(0, 16)
    input.BackgroundColor3 = colors.control; input.TextColor3 = colors.text; input.BorderSizePixel = 0
    input.Font = Enum.Font.Gotham; input.TextSize = 14; input.Parent = parent; rounded(input)
    input:GetPropertyChangedSignal("Text"):Connect(changed)
    return function() return tonumber((input.Text:gsub(",", "."))) end
end
local function wrap(value: number, delta: number, maximum: number): number
    return (value - 1 + delta) % maximum + 1
end

function Controller.Start()
    if started or not RunService:IsStudio() or not Access.ClientAllowed() then return end
    started = true
    task.spawn(function()
        local player = Players.LocalPlayer
        local playerGui = player:WaitForChild("PlayerGui")
        local gui = Instance.new("ScreenGui")
        gui.Name = "Game1GameplayTestGui"; gui.ResetOnSpawn = false; gui.DisplayOrder = 43; gui.Parent = playerGui
        local launcher = button(gui, "GP", UDim2.fromOffset(44, 44))
        launcher:SetAttribute("DebugTooltip", "Gameplay · monster / equipment test")
        launcher.Position = StudioDebugDock.ButtonPosition(PANEL_ID)
        local panel = Instance.new("Frame")
        panel.Name = "Panel"
        panel.AnchorPoint = Vector2.new(0, 1); panel.Position = UDim2.new(0, 8, 1, -8)
        panel.Size = UDim2.fromOffset(PANEL_WIDTH, PANEL_HEIGHT); panel.BackgroundColor3 = colors.panel; panel.BorderSizePixel = 0; panel.Visible = false; panel.Active = true; panel.Parent = gui; rounded(panel)
        local constraint = Instance.new("UISizeConstraint"); constraint.MaxSize = Vector2.new(PANEL_WIDTH, PANEL_HEIGHT); constraint.Parent = panel
        local title = label(panel, "GAMEPLAY TEST", UDim2.new(1, -60, 0, 28)); title.Position = UDim2.fromOffset(12, 3); title.Font = Enum.Font.GothamBold
        local close = button(panel, "×", UDim2.fromOffset(30, 28)); close.AnchorPoint = Vector2.new(1, 0); close.Position = UDim2.new(1, -8, 0, 4)
        local body = Instance.new("ScrollingFrame")
        body.Name = "Body"; body.ScrollingDirection = Enum.ScrollingDirection.Y
        body.Position = UDim2.fromOffset(10, 36); body.Size = UDim2.new(1, -20, 1, -64); body.AutomaticCanvasSize = Enum.AutomaticSize.Y
        body.CanvasSize = UDim2.fromOffset(0, 0); body.ScrollBarThickness = 5; body.BackgroundTransparency = 1; body.BorderSizePixel = 0; body.Active = true; body.Parent = panel
        local layout = Instance.new("UIListLayout"); layout.Padding = UDim.new(0, 4); layout.SortOrder = Enum.SortOrder.LayoutOrder; layout.Parent = body
        local status = label(panel, "Enter test to begin", UDim2.new(1, -20, 0, 26)); status.Position = UDim2.new(0, 10, 1, -27); status.TextColor3 = colors.muted
        local level, monsterLevel, count, upgrade = 1, 1, 1, 0
        local monsterType = "melee"
        local skilledIndex = 1
        local weapons = {{id="", level=1, type="hands", damage=0}}
        for _, entry in ipairs(Balance.Weapons) do table.insert(weapons, entry) end
        table.sort(weapons, function(a,b) if a.level == b.level then return a.id < b.id end return a.level < b.level end)
        local weaponIndex, armorIndex = 2, 1
        local function weapon() return weapons[weaponIndex] end
        local function armor() return Balance.Armors[armorIndex] end
        local function minimumLevel(): number
            local _, required = Balance.Grade.ForLevel(weapon().level)
            return math.max(required, armor().level)
        end
        local first = row(body, 46); horizontal(first)
        local refreshLevel = picker(cell(first, "Level"), "Level", function()
            return ("LVL %d\n%d HP"):format(level, Balance.Level(level).hp)
        end, function(d) level = math.clamp(level + d, minimumLevel(), Balance.MaxLevel) end)
        local function ensureLevel()
            level = math.max(level, minimumLevel()); refreshLevel()
        end
        local refreshUpgrade: (() -> ())? = nil
        local refreshCrit: (() -> ())? = nil
        picker(cell(first, "Weapon"), "Weapon", function()
            local w = weapon(); local grade, required = Balance.Grade.ForLevel(w.level)
            return if w.id == "" then "Hands" else ("%s %s\n%s · req %d"):format(w.id:sub(-3), w.type, grade, required)
        end, function(d)
            weaponIndex=wrap(weaponIndex,d,#weapons); ensureLevel()
            if refreshUpgrade then refreshUpgrade() end
            if refreshCrit then refreshCrit() end
        end)
        local second = row(body, 46); horizontal(second)
        picker(cell(second, "Armor"), "Armor", function()
            local a=armor(); return ("LVL %d\n+%d HP"):format(a.level,a.hp)
        end, function(d) armorIndex=wrap(armorIndex,d,#Balance.Armors); ensureLevel() end)
        refreshUpgrade = picker(cell(second, "Upgrade"), "Upgrade", function()
            return ("+%d\n%d ATK"):format(upgrade, Balance.Rules.baseDamage + Balance.WeaponDamage(weapon(),upgrade))
        end, function(d) upgrade=wrap(upgrade+1,d,Balance.Rules.maxUpgrade+1)-1 end)
        local third = row(body, 46); horizontal(third)
        local monsterCell = cell(third, "Monster")
        local function selectedMonster()
            if monsterType == "skilled" then return Balance.SkilledMonsters[skilledIndex] end
            return assert(Balance.MonsterAt(monsterLevel, monsterType))
        end
        local refreshMonster = picker(monsterCell, "Monster", function()
            local m=selectedMonster()
            if m.skills then
                local skill = Balance.Skill(m.skills[1].skillId)
                return ("%s%s · LVL %d\n%d HP · %d ATK"):format(skill.name,if #m.skills>1 then " +"..(#m.skills-1) else "",m.level,m.hp,m.damage)
            end
            return ("LVL %d · %d HP\n%d ATK · %g studs"):format(m.level,m.hp,m.damage,m.attackRange)
        end, function(d)
            if monsterType=="skilled" then skilledIndex=wrap(skilledIndex,d,#Balance.SkilledMonsters)
            else monsterLevel=wrap(monsterLevel,d,Balance.MaxLevel) end
        end)
        local kindButton = contentButton(monsterCell, "Skilled", 15)
        kindButton.Text = "Melee"; kindButton.TextSize = 11
        kindButton.AnchorPoint = Vector2.new(1, 0); kindButton.Position = UDim2.new(1, 0, 0, 0); kindButton.ZIndex = 2
        kindButton.Activated:Connect(function()
            monsterType = if monsterType == "melee" then "ranged" elseif monsterType=="ranged" and Balance.Test.skilledEnabled and #Balance.SkilledMonsters>0 then "skilled" else "melee"
            kindButton.Text = if monsterType == "melee" then "Melee" elseif monsterType=="ranged" then "Ranged" else "Skilled"
            refreshMonster()
        end)
        local group = cell(third, "Group")
        local start = contentButton(group, "Start", 30); start.BackgroundColor3=colors.accent
        start.AnchorPoint = Vector2.new(1, 0); start.Position = UDim2.new(1, 0, 0, 16)
        picker(group, "Group size", function() return tostring(count) end, function(d) count=wrap(count,d,Balance.Test.maxGroup) end, start.Size.X.Offset + 4)
        local recoveryRow = row(body, 46); horizontal(recoveryRow)
        local invoke: (string) -> ()
        local recoveryRevision = 0
        local function recoveryChanged()
            recoveryRevision += 1
            local revision = recoveryRevision
            if not player:GetAttribute("Game1GameplayTestActive") then return end
            -- Coalesce field focus loss and checkbox taps. A loadout action carries both rates itself.
            task.delay(0.4, function()
                if revision == recoveryRevision and player:GetAttribute("Game1GameplayTestActive") then invoke("recovery") end
            end)
        end
        local readRegen = recoveryField(cell(recoveryRow, "Regeneration"), "Regen · HP/sec", recoveryChanged)
        local readVampiric = recoveryField(cell(recoveryRow, "Vampiric"), "Vampiric · %", recoveryChanged)
        local critRow = row(body, 46); horizontal(critRow)
        local function critChanged() if refreshCrit then refreshCrit() end end
        local readCritPercent = numericField(cell(critRow, "CritPercent"), "Crit buff · %", 0, critChanged)
        local readCritFlat = numericField(cell(critRow, "CritFlat"), "Crit bonus · pp", 0, critChanged)
        local critDamageRow = row(body, 46); horizontal(critDamageRow)
        local readCritMultiplier = numericField(cell(critDamageRow, "CritMultiplier"), "Crit damage · ×", Balance.Rules.critMultiplier, critChanged)
        local preview = cell(critDamageRow, "CritPreview")
        local previewTitle = label(preview, "Effective crit", UDim2.new(1, 0, 0, 15)); previewTitle.TextColor3 = colors.muted; previewTitle.TextSize = 12
        local previewValue = label(preview, "", UDim2.new(1, 0, 0, 30)); previewValue.Position = UDim2.fromOffset(0, 16)
        refreshCrit = function()
            local percent, flat, multiplier = readCritPercent(), readCritFlat(), readCritMultiplier()
            if not percent or not flat or not multiplier or not Critical.ValidateTest(percent, flat, multiplier) then previewValue.Text = "Invalid"; return end
            local base = if weapon().id == "" then Balance.Rules.critChance else weapon().critChance
            previewValue.Text = ("%.1f%% · ×%.2f"):format(Critical.Chance(base, percent, flat), multiplier)
        end
        refreshCrit()
        local busy = false
        local queuedAction: string? = nil
        local queuedRecovery = false
        local lastRequestAt = -math.huge
        local closeOnSuccess = {enter=true, apply=true, start=true, visit=true, exit=true}
        invoke = function(action: string)
            if action == "enter" or action == "apply" or action == "start" or action == "exit" then
                recoveryRevision += 1
                queuedRecovery = false
            end
            if busy then
                -- Keep an explicit action ahead of automatic recovery; never drop Apply on focus loss.
                if action == "recovery" then queuedRecovery = true else queuedAction = action end
                return
            end
            if action == "recovery" and not player:GetAttribute("Game1GameplayTestActive") then return end
            local remotes = RS:FindFirstChild("Game1Remotes")
            local remote = remotes and remotes:FindFirstChild("GameplayTest")
            if not remote or not remote:IsA("RemoteFunction") then
                status.Text = "Gameplay server not ready · retry"
                return
            end
            local regen, vampiric = readRegen(), readVampiric()
            if action == "enter" or action == "apply" or action == "start" or action == "recovery" then
                if not regen or not (regen >= 0 and regen <= 10000) or not vampiric or not (vampiric >= 0 and vampiric <= 100) then
                    status.Text = "HP/sec: 0–10000 · Vampiric: 0–100%"
                    return
                end
            end
            local critPercent, critFlat, critMultiplier = readCritPercent(), readCritFlat(), readCritMultiplier()
            if action == "enter" or action == "apply" or action == "start" then
                local valid, reason = Critical.ValidateTest(critPercent, critFlat, critMultiplier)
                if not valid then status.Text = tostring(reason); return end
            end
            busy = true; status.Text = "Working…"
            local payload = {level=level,weapon=weapon().id,armor=armor().id,upgrade=upgrade,monsterId=selectedMonster().id,count=count,regen=regen,vampiric=vampiric,critPercent=critPercent,critFlat=critFlat,critMultiplier=critMultiplier}
            task.spawn(function()
                -- Respect the server's 0.35 second minimum between requests.
                local delaySeconds = 0.4 - (os.clock() - lastRequestAt)
                if delaySeconds > 0 then task.wait(delaySeconds) end
                lastRequestAt = os.clock()
                local ok, response = pcall(function() return remote:InvokeServer(action,payload) end)
                if ok and type(response)=="table" then
                    status.Text = tostring(response.message or "")
                    if response.ok and closeOnSuccess[action] and playerGui:GetAttribute(OPEN) == PANEL_ID then playerGui:SetAttribute(OPEN, "") end
                else status.Text = "Gameplay Test request failed" end
                busy = false
                local nextAction = queuedAction; queuedAction = nil
                if nextAction then
                    invoke(nextAction)
                elseif queuedRecovery then
                    queuedRecovery = false; invoke("recovery")
                end
            end)
        end
        local actions = row(body, 30); horizontal(actions)
        -- Allocate for the longer label so switching Enter / Apply never shifts siblings.
        local enterButton = contentButton(actions, "Apply loadout", 30); enterButton.BackgroundColor3 = colors.accent
        enterButton.Activated:Connect(function() invoke(if player:GetAttribute("Game1GameplayTestActive") then "apply" else "enter") end)
        local stop = contentButton(actions, "Stop group", 30); stop.Activated:Connect(function() invoke("stop") end)
        local exitButton = contentButton(actions, "Exit", 30); exitButton.Activated:Connect(function() invoke("exit") end)
        local navigation = row(body, 30)
        local visit = contentButton(navigation, "Go", 30); visit.Activated:Connect(function() invoke("visit") end)
        start.Activated:Connect(function() invoke("start") end)
        local function refresh()
            local inWorld = player.Character ~= nil and playerGui:GetAttribute("Game1CharacterSceneInputBlocked") ~= true
            gui.Enabled = inWorld
            panel.Visible = inWorld and playerGui:GetAttribute(OPEN) == PANEL_ID
            enterButton.Text = if player:GetAttribute("Game1GameplayTestActive") then "Apply loadout" else "Enter test"
        end
        launcher.Activated:Connect(function() playerGui:SetAttribute(OPEN, if panel.Visible then "" else PANEL_ID) end)
        close.Activated:Connect(function() playerGui:SetAttribute(OPEN, "") end)
        playerGui:GetAttributeChangedSignal(OPEN):Connect(refresh)
        playerGui:GetAttributeChangedSignal("Game1CharacterSceneInputBlocked"):Connect(refresh)
        player:GetAttributeChangedSignal("Game1GameplayTestActive"):Connect(refresh)
        player:GetPropertyChangedSignal("Character"):Connect(refresh)
        StudioDebugDock.Bind(PANEL_ID, launcher, panel, PANEL_WIDTH, true, PANEL_HEIGHT)
        refresh()
        print("[game1][gameplay-test] GP launcher ready · Studio only")
    end)
end
return table.freeze(Controller)
