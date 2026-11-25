--!strict
-- One controlled Studio arena per server. Never grants persistent items, XP or gold.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local RS = game:GetService("ReplicatedStorage")
local Shared = RS:WaitForChild("Game1Shared")
local Balance = require(Shared:WaitForChild("balance"):WaitForChild("Balance"))
local Access = require(Shared:WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local CharacterService = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CharacterService"))
local Weapons = require(script.Parent.Parent:WaitForChild("weapon"):WaitForChild("WeaponEquipService"))
local Spawner = require(script.Parent.Parent:WaitForChild("monster"):WaitForChild("MonsterSpawnerService"))
local Loadout = require(script.Parent:WaitForChild("GameplayTestLoadout"))
local Arena = require(script.Parent:WaitForChild("GameplayTestArena"))
local CharacterConfig = require(Shared:WaitForChild("character"):WaitForChild("CharacterConfig"))
local Service = {}
local session: any = nil
local started = false
local busy: {[Player]: boolean} = {}
local last: {[Player]: number} = {}
local function result(ok: boolean, message: string)
    return {ok=ok, message=message}
end
local function allowed(player: Player): boolean
    return RunService:IsStudio() and Access.ServerAllowed(player)
end
local function alive(player: Player): Model?
    local character = player.Character
    return if character and character.Parent and character:GetAttribute("LifeState") == "Alive" then character else nil
end
local function active(s: any): boolean
    return session == s and s.player.Parent == Players
end
local function clearGroup(s: any)
    s.generation += 1
    Arena.Clear(s.group)
    s.groupSupports:ClearAllChildren()
end
local function clearSession(s: any)
    if session == s then session = nil end
    if s.trackConnection then s.trackConnection:Disconnect(); s.trackConnection = nil end
    local character = s.player.Character
    if character then character:SetAttribute("GameplayTestOnTrack", nil) end
    clearGroup(s)
    Arena.Clear(s.line)
    s.folder:Destroy()
    if s.deathConnection then s.deathConnection:Disconnect() end
    Loadout.Set(s.player, nil)
end
-- One server-side zone check for the owner, not 35 Touched listeners.
local function bindTrack(s: any)
    local elapsed = 0
    s.trackConnection = RunService.Heartbeat:Connect(function(dt)
        elapsed += dt
        if elapsed < 0.1 then return end
        elapsed = 0
        if not active(s) then return end
        local character = s.player.Character
        if not character then return end
        local root = character:FindFirstChild("RootCollider")
        local onTrack = character:GetAttribute("LifeState") == "Alive"
            and character:GetAttribute("GameplayTestKind") == "player"
            and character:GetAttribute("Game1GameplayTestOwner") == s.player.UserId
            and root ~= nil and root:IsA("BasePart")
            and Arena.IsOnTrack(s.trackTop, s.trackSize, root.Position)
        if (character:GetAttribute("GameplayTestOnTrack") == true) ~= onTrack then
            character:SetAttribute("GameplayTestOnTrack", if onTrack then true else nil)
        end
    end)
end
local function bindCharacter(s: any, character: Model)
    if s.deathConnection then s.deathConnection:Disconnect() end
    s.deathConnection = character:GetAttributeChangedSignal("LifeState"):Connect(function()
        if active(s) and character:GetAttribute("LifeState") == "Dying" then
            character:SetAttribute("GameplayTestOnTrack", nil)
            clearGroup(s)
        end
    end)
end
local function enter(player: Player, selection: any)
    if session then return result(false, "Arena is already occupied") end
    local character = alive(player)
    if not character or character:GetAttribute("InCombat") == true then return result(false, "Enter the world and leave combat first") end
    local size = Spawner.TestTemplateSize()
    if not size then return result(false, "Gremlin template is not synced into ServerStorage") end
    local root = character:FindFirstChild("RootCollider")
    if not root or not root:IsA("BasePart") then return result(false, "RootCollider is missing") end
    local s = {player=player, normalFrame=root.CFrame, normalWeapon=tostring(character:GetAttribute("EquippedWeaponSlug") or ""),
        archetype=tostring(character:GetAttribute("CharacterArchetype") or ""), line={}, group={}, size=size, generation=0, spacing=Arena.Spacing(size)}
    local folder = Instance.new("Folder")
    folder.Name = "Game1GameplayTest"; folder.Parent = workspace
    s.folder = folder
    local groupSupports = Instance.new("Folder"); groupSupports.Name = "GroupSupports"; groupSupports.Parent = folder; s.groupSupports = groupSupports
    local origin = Loadout.Origin()
    s.trackTop, s.trackSize = Arena.BuildLinePlatform(folder, origin, #Balance.Monsters, s.spacing, size)
    session = s
    bindTrack(s)
    Loadout.Set(player, selection)
    local replacement = CharacterService.Respawn(player, s.archetype)
    if not replacement or not active(s) then
        if active(s) then clearSession(s) end
        return result(false, "Cannot spawn test character")
    end
    bindCharacter(s, replacement)
    if replacement:GetAttribute("GameplayTestError") then return result(false, "Weapon unavailable; change loadout or Exit") end
    Arena.ShowWeapons(folder, origin, replacement)
    local count = 0
    for index, row in ipairs(Balance.Monsters) do
        if not active(s) then return result(false, "Test cancelled") end
        local point = Arena.LinePoint(origin, index, s.spacing)
        local monster = Arena.Add(player, row, "line", point, -origin.LookVector, s.line, s.folder)
        if monster then count += 1 end
    end
    return result(count == #Balance.Monsters, ("Line: %d/%d · spacing %d studs"):format(count, #Balance.Monsters, s.spacing))
end
local function apply(s: any, selection: any)
    local character = alive(s.player)
    if not character then return result(false, "Respawn first") end
    if character:GetAttribute("AttackEndsAt") ~= nil then return result(false, "Finish current attack first") end
    clearGroup(s)
    local previous = Loadout.Get(s.player)
    Loadout.Set(s.player, selection)
    local ok, reason = Loadout.Apply(s.player, character)
    if not ok then
        Loadout.Set(s.player, previous)
        if previous then Loadout.Apply(s.player, character) end
        return result(false, tostring(reason))
    end
    return result(true, if selection.placeholder then "Applied · 2H sword visual placeholder" else "Loadout applied")
end
local function startGroup(s: any, level: number, count: number)
    local character = alive(s.player)
    if not character then return result(false, "Respawn first") end
    clearGroup(s)
    local generation = s.generation
    local origin = Loadout.Origin()
    Arena.Warp(character, origin)
    character:SetAttribute("HP", character:GetAttribute("MaxHP"))
    local row = Balance.Monsters[level]
    local models = {}
    local function current(): boolean
        return active(s) and s.generation == generation and alive(s.player) == character
    end
    for index = 1, count do
        if not current() then return result(false, "Encounter cancelled") end
        local point = Arena.GroupPoint(origin, index, count, s.size)
        local model = Arena.Add(s.player, row, "group", point, origin.Position - point, s.group, s.groupSupports)
        if not current() then return result(false, "Encounter cancelled") end
        if not model then clearGroup(s); return result(false, "Group spawn failed") end
        table.insert(models, model)
    end
    -- All members must be present and out of spawn presentation before aggro.
    local deadline = os.clock() + 12
    while current() do
        local ready = true
        for _, model in ipairs(models) do
            if not model.Parent then clearGroup(s); return result(false, "Group member disappeared") end
            if model:GetAttribute("MonsterSpawning") == true or model:GetAttribute("Damageable") ~= true then ready = false end
        end
        if ready then
            for _, model in ipairs(models) do
                model:SetAttribute("GameplayTestArmed", true)
                model:SetAttribute("MonsterAggressive", true)
            end
            return result(true, ("Group started: %d × LVL %d"):format(count, level))
        end
        if os.clock() >= deadline then clearGroup(s); return result(false, "Group readiness timeout") end
        task.wait(0.05)
    end
    return result(false, "Encounter cancelled")
end
local function exit(s: any)
    if not alive(s.player) then return result(false, "Respawn first") end
    clearGroup(s)
    local previous = Loadout.Get(s.player)
    Loadout.Set(s.player, nil)
    local replacement = CharacterService.Respawn(s.player, s.archetype, s.normalFrame)
    if not replacement then
        if active(s) then Loadout.Set(s.player, previous) end
        return result(false, "Cannot restore normal character")
    end
    if s.normalWeapon == "" then Weapons.Unequip(replacement) else Weapons.Equip(replacement, s.normalWeapon) end
    clearSession(s)
    return result(true, "Normal character restored")
end
local function validInt(value: any, maximum: number): boolean
    return type(value) == "number" and value >= 1 and value <= maximum and value % 1 == 0
end
local function dispatch(player: Player, action: any, request: any)
    if not allowed(player) then return result(false, "Studio debug access only") end
    if type(request) ~= "table" then return result(false, "Invalid request") end
    if action == "enter" then
        local selection, reason = Loadout.Validate(request)
        if not selection then return result(false, tostring(reason)) end
        return enter(player, selection)
    end
    local s = session
    if not s or s.player ~= player then return result(false, "Enter Gameplay Test first") end
    if action == "exit" then return exit(s) end
    if action == "recovery" then
        local character = alive(player)
        if not character then return result(false, "Respawn first") end
        local ok, reason = Loadout.SetRecovery(player, character, request.regen, request.vampiric)
        return result(ok, if ok then "Recovery settings applied" else tostring(reason))
    end
    if action == "stop" then clearGroup(s); return result(true, "Group cleared") end
    if action == "apply" or action == "start" then
        local selection, reason = Loadout.Validate(request)
        if not selection then return result(false, tostring(reason)) end
        if action == "start" and (not validInt(request.monsterLevel, #Balance.Monsters) or not validInt(request.count, Balance.Test.maxGroup)) then return result(false, "Invalid group") end
        local applied = apply(s, selection)
        if not applied.ok or action == "apply" then return applied end
        return startGroup(s, request.monsterLevel, request.count)
    end
    if action == "visit" and validInt(request.monsterLevel, #Balance.Monsters) then
        local character = alive(player)
        if not character then return result(false, "Respawn first") end
        if character:GetAttribute("AttackEndsAt") ~= nil then return result(false, "Finish current attack first") end
        clearGroup(s)
        local origin = Loadout.Origin()
        local point = Arena.LinePoint(origin, request.monsterLevel, s.spacing) - origin.LookVector * 5
        Arena.Warp(character, CFrame.new(point + Vector3.new(0, CharacterConfig.RootAnchorOffset, 0)) * origin.Rotation)
        return result(true, "At selected monster")
    end
    return result(false, "Unknown action")
end
function Service.Start()
    if started or not RunService:IsStudio() then return end
    started = true
    local remote = Instance.new("RemoteFunction")
    remote.Name = "GameplayTest"
    remote.OnServerInvoke = function(player, action, request)
        if not allowed(player) then return result(false, "Studio debug access only") end
        if busy[player] then return result(false, "Test operation in progress") end
        local now = os.clock()
        if now - (last[player] or -math.huge) < 0.35 then return result(false, "Try again") end
        last[player] = now
        busy[player] = true
        local ok, response = pcall(dispatch, player, action, request)
        busy[player] = nil
        if not ok then
            warn("[game1][gameplay-test] " .. tostring(response))
            if session and session.player == player then clearGroup(session) end
            return result(false, "Operation failed; see server log")
        end
        return response
    end
    remote.Parent = RS:WaitForChild("Game1Remotes")
    local function bindPlayer(player: Player)
        player.CharacterRemoving:Connect(function(character)
            local s = session
            if s and s.player == player and character:GetAttribute("GameplayTestKind") == "player" then
                clearGroup(s) -- also cancels a group still being constructed on void recovery
            end
        end)
        player.CharacterAdded:Connect(function(character)
            local s = session
            if s and s.player == player and character:GetAttribute("GameplayTestKind") == "player" then bindCharacter(s, character) end
        end)
    end
    Players.PlayerAdded:Connect(bindPlayer)
    for _, player in ipairs(Players:GetPlayers()) do bindPlayer(player) end
    Players.PlayerRemoving:Connect(function(player)
        if session and session.player == player then clearSession(session) end
        last[player] = nil; busy[player] = nil
    end)
    print("[game1][gameplay-test] ready · Studio only")
end
return table.freeze(Service)
