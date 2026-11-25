--!strict
-- Studio gameplay laboratory. Every mutation is validated by GameplayTestService.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local RS = game:GetService("ReplicatedStorage")
local StudioDebugDock = require(script.Parent:WaitForChild("StudioDebugDock"))
local Shared = RS:WaitForChild("Game1Shared")
local Balance = require(Shared:WaitForChild("balance"):WaitForChild("Balance"))
local Access = require(Shared:WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local Controller = {}
local started = false
local PANEL_ID = "GP"
local OPEN = "Game1DebugPanelOpen"
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
    b.Parent = parent; rounded(b)
    return b
end
local function label(parent: Instance, text: string, size: UDim2): TextLabel
    local l = Instance.new("TextLabel")
    l.Text = text; l.Size = size; l.BackgroundTransparency = 1; l.TextColor3 = colors.text
    l.Font = Enum.Font.Gotham; l.TextSize = 13; l.TextXAlignment = Enum.TextXAlignment.Left
    l.TextWrapped = true; l.Parent = parent
    return l
end
local function row(parent: Instance, height: number): Frame
    local f = Instance.new("Frame")
    f.BackgroundTransparency = 1; f.Size = UDim2.new(1, -8, 0, height); f.Parent = parent
    return f
end
local function picker(parent: Instance, caption: string, read: () -> string, adjust: (number) -> ())
    local f = row(parent, 54)
    local title = label(f, caption, UDim2.new(1, 0, 0, 17)); title.TextColor3 = colors.muted
    local previous = button(f, "‹", UDim2.fromOffset(38, 34)); previous.Position = UDim2.fromOffset(0, 19)
    local nextButton = button(f, "›", UDim2.fromOffset(38, 34)); nextButton.AnchorPoint = Vector2.new(1, 0); nextButton.Position = UDim2.new(1, 0, 0, 19)
    local current = label(f, "", UDim2.new(1, -86, 0, 34)); current.Position = UDim2.fromOffset(43, 19); current.TextXAlignment = Enum.TextXAlignment.Center
    local function refresh() current.Text = read() end
    previous.Activated:Connect(function() adjust(-1); refresh() end)
    nextButton.Activated:Connect(function() adjust(1); refresh() end)
    refresh()
    return refresh
end
local function numericField(parent: Instance, caption: string): TextBox
    local f = row(parent, 54)
    local title = label(f, caption, UDim2.new(1, 0, 0, 17)); title.TextColor3 = colors.muted
    local input = Instance.new("TextBox")
    input.Text = "0"; input.ClearTextOnFocus = false; input.PlaceholderText = "0 = off"
    input.Size = UDim2.new(1, 0, 0, 34); input.Position = UDim2.fromOffset(0, 19)
    input.BackgroundColor3 = colors.control; input.TextColor3 = colors.text; input.BorderSizePixel = 0
    input.Font = Enum.Font.Gotham; input.TextSize = 14; input.Parent = f; rounded(input)
    return input
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
        panel.Position = StudioDebugDock.WindowPosition(PANEL_ID, 440)
        panel.Size = UDim2.new(1, -20, 1, -100); panel.BackgroundColor3 = colors.panel; panel.BorderSizePixel = 0; panel.Visible = false; panel.Active = true; panel.Parent = gui; rounded(panel)
        local constraint = Instance.new("UISizeConstraint"); constraint.MaxSize = Vector2.new(440, 585); constraint.Parent = panel
        local title = label(panel, "GAMEPLAY TEST", UDim2.new(1, -60, 0, 36)); title.Position = UDim2.fromOffset(12, 3); title.Font = Enum.Font.GothamBold
        local close = button(panel, "×", UDim2.fromOffset(38, 36)); close.AnchorPoint = Vector2.new(1, 0); close.Position = UDim2.new(1, -8, 0, 4)
        local body = Instance.new("ScrollingFrame")
        body.Position = UDim2.fromOffset(12, 46); body.Size = UDim2.new(1, -24, 1, -90); body.AutomaticCanvasSize = Enum.AutomaticSize.Y
        body.CanvasSize = UDim2.fromOffset(0, 0); body.ScrollBarThickness = 5; body.BackgroundTransparency = 1; body.BorderSizePixel = 0; body.Active = true; body.Parent = panel
        local layout = Instance.new("UIListLayout"); layout.Padding = UDim.new(0, 6); layout.SortOrder = Enum.SortOrder.LayoutOrder; layout.Parent = body
        local status = label(panel, "Enter test to begin", UDim2.new(1, -24, 0, 40)); status.Position = UDim2.new(0, 12, 1, -42); status.TextColor3 = colors.muted
        local level, monsterLevel, count, upgrade = 1, 1, 1, 0
        local weapons = {{id="", level=1, type="hands", damage=0}}
        for _, entry in ipairs(Balance.Weapons) do table.insert(weapons, entry) end
        table.sort(weapons, function(a,b) if a.level == b.level then return a.id < b.id end return a.level < b.level end)
        local weaponIndex, armorIndex = 2, 1
        local function weapon() return weapons[weaponIndex] end
        local function armor() return Balance.Armors[armorIndex] end
        picker(body, "Character level", function() return ("LVL %d · %d base HP"):format(level, Balance.Level(level).hp) end, function(d) level=wrap(level,d,#Balance.Monsters) end)
        local refreshUpgrade: (() -> ())? = nil
        picker(body, "Weapon · grade / required LVL", function()
            local w = weapon(); local grade, required = Balance.Grade.ForLevel(w.level)
            return if w.id == "" then "Hands" else ("Оружие_%s · %s · %s · req %d"):format(w.id:sub(-3), w.type, grade, required)
        end, function(d) weaponIndex=wrap(weaponIndex,d,#weapons); if refreshUpgrade then refreshUpgrade() end end)
        refreshUpgrade = picker(body, "Upgrade", function() return ("+%d · ATK %d"):format(upgrade, Balance.Rules.baseDamage + Balance.WeaponDamage(weapon(),upgrade)) end, function(d) upgrade=wrap(upgrade+1,d,Balance.Rules.maxUpgrade+1)-1 end)
        picker(body, "Armor", function() local a=armor(); return ("Броня_%s · LVL %d · +%d HP"):format(a.id:sub(-3),a.level,a.hp) end, function(d) armorIndex=wrap(armorIndex,d,#Balance.Armors) end)
        picker(body, "Monster", function() local m=Balance.Monsters[monsterLevel]; return ("Монстр_%03d · LVL %d · %d HP / %d ATK"):format(monsterLevel,monsterLevel,m.hp,m.damage) end, function(d) monsterLevel=wrap(monsterLevel,d,#Balance.Monsters) end)
        picker(body, "Group size", function() return tostring(count) end, function(d) count=wrap(count,d,Balance.Test.maxGroup) end)
        local regenInput = numericField(body, "Regeneration · HP/sec (0 = off)")
        local vampiricInput = numericField(body, "Vampiric · % of damage (0 = off)")
        local busy = false
        local function invoke(action: string)
            if busy then return end
            local remotes = RS:FindFirstChild("Game1Remotes")
            local remote = remotes and remotes:FindFirstChild("GameplayTest")
            if not remote or not remote:IsA("RemoteFunction") then
                status.Text = "Gameplay server not ready · retry"
                return
            end
            local regen = tonumber((regenInput.Text:gsub(",", ".")))
            local vampiric = tonumber((vampiricInput.Text:gsub(",", ".")))
            if action == "enter" or action == "apply" or action == "start" or action == "recovery" then
                if not regen or not (regen >= 0 and regen <= 10000) or not vampiric or not (vampiric >= 0 and vampiric <= 100) then
                    status.Text = "HP/sec: 0–10000 · Vampiric: 0–100%"
                    return
                end
            end
            busy = true; status.Text = "Working…"
            local payload = {level=level,weapon=weapon().id,armor=armor().id,upgrade=upgrade,monsterLevel=monsterLevel,count=count,regen=regen,vampiric=vampiric}
            task.spawn(function()
                local ok, response = pcall(function() return remote:InvokeServer(action,payload) end)
                if ok and type(response)=="table" then
                    status.Text = tostring(response.message or "")
                    if response.ok and playerGui:GetAttribute(OPEN) == PANEL_ID and (action == "start" or action == "visit" or action == "exit") then playerGui:SetAttribute(OPEN, "") end
                else status.Text = "Gameplay Test request failed" end
                busy = false
            end)
        end
        local enterButton = button(body, "Enter test / Apply loadout", UDim2.new(1,-8,0,40)); enterButton.BackgroundColor3 = colors.accent
        enterButton.Activated:Connect(function() invoke(if player:GetAttribute("Game1GameplayTestActive") then "apply" else "enter") end)
        local recoveryButton = button(body, "Apply recovery", UDim2.new(1,-8,0,40))
        recoveryButton.Activated:Connect(function() invoke("recovery") end)
        local visit = button(body, "Visit passive monster", UDim2.new(1,-8,0,40)); visit.Activated:Connect(function() invoke("visit") end)
        local start = button(body, "Start group", UDim2.new(1,-8,0,40)); start.BackgroundColor3=colors.accent; start.Activated:Connect(function() invoke("start") end)
        local stop = button(body, "Stop group", UDim2.new(1,-8,0,40)); stop.Activated:Connect(function() invoke("stop") end)
        local exitButton = button(body, "Exit test", UDim2.new(1,-8,0,40)); exitButton.Activated:Connect(function() invoke("exit") end)
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
        StudioDebugDock.Bind(PANEL_ID, launcher, panel, 440, true)
        refresh()
        print("[game1][gameplay-test] GP launcher ready · Studio only")
    end)
end
return table.freeze(Controller)
