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
local Report = require(script.Parent:WaitForChild("GameplayCombatReport"))
local Plan = require(script.Parent:WaitForChild("GameplayGuidedPlan"))
local RuntimeVersion = require(Shared:WaitForChild("RuntimeVersion"))
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
local function publishGuide(s: any, message: string)
    s.player:SetAttribute("GameplayGuideStatus", message)
end
local function finishTrial(s: any, outcome: string)
    local row=Report.Finish(outcome)
    if not row or not s.guide then return end
    s.guide.running=false
    local character=s.player.Character
    if character then character:SetAttribute("GameplayGuideTrial",nil) end
    if outcome=="interrupted" then publishGuide(s,"Interrupted · retry this trial"); return end
    table.insert(s.guide.results,row)
    local total=#s.guide.stages; local done=#s.guide.results
    publishGuide(s,("%d/%d · %s · %.1f DPS · %.1fs · HP %d/%d%s"):format(done,total,outcome,row.dps,row.seconds,row.hpLeft,row.maxHP,if done==total then " · Done" else " · Next"))
end
local function clearGroup(s: any)
    if s.guide and s.guide.running then finishTrial(s, Report.Outcome() or "interrupted") end
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
    s.player:SetAttribute("GameplayGuideStatus", nil)
end
-- One server-side zone check for the owner, not 35 Touched listeners.
local function bindTrack(s: any)
    local elapsed = 0
    s.trackConnection = RunService.Heartbeat:Connect(function(dt)
        elapsed += dt
        if elapsed < 0.1 then return end
        local sample=elapsed
        elapsed = 0
        if not active(s) then return end
        if s.guide and s.guide.running then
            Report.Sample(sample)
            local outcome=Report.Outcome()
            if outcome then finishTrial(s,outcome); clearGroup(s) end
        end
        local character = s.player.Character
        if not character then return end
        local root = character:FindFirstChild("RootCollider")
        local eligible = character:GetAttribute("LifeState") == "Alive"
            and character:GetAttribute("GameplayTestKind") == "player"
            and character:GetAttribute("Game1GameplayTestOwner") == s.player.UserId
            and root ~= nil and root:IsA("BasePart")
        local onTrack = false
        if eligible and root and root:IsA("BasePart") and not (s.guide and s.guide.running) then
            for _, track in ipairs(s.layout.tracks) do
                if Arena.IsOnTrack(track.top, track.size, root.Position) then onTrack = true; break end
            end
        end
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
    s.layout = Arena.BuildLinePlatform(folder, origin, s.spacing, size)
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
    Arena.ShowWeapons(folder, s.layout.weaponOrigin, replacement)
    local count = 0
    local rows = table.clone(Balance.Monsters)
    if Balance.Test.skilledEnabled then for _, row in ipairs(Balance.SkilledMonsters) do table.insert(rows,row) end end
    for _, row in ipairs(rows) do
        if not active(s) then return result(false, "Test cancelled") end
        local slot = s.layout.slots[row.id]
        local monster = Arena.Add(player, row, "line", slot.point, slot.facing, s.line, s.folder, slot)
        if monster then count += 1 end
    end
    return result(count == #rows, ("Line: %d/%d · spacing %d studs"):format(count, #rows, s.spacing))
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
    return result(true, if selection.weapon and selection.weapon.type == "dualswords" and character:GetAttribute("AnimationWeaponSet") == "1hs" then "Applied · dualswords 1hs animation preview" elseif selection.placeholder then "Applied · sword visual placeholder" else "Loadout applied")
end
local function startGroup(s: any, row: any, count: number, stage: any?)
    local character = alive(s.player)
    if not character then return result(false, "Respawn first") end
    clearGroup(s)
    local generation = s.generation
    local origin = Loadout.Origin()
    Arena.Warp(character, origin)
    character:SetAttribute("HP", character:GetAttribute("MaxHP"))
    local models = {}
    local function current(): boolean
        return active(s) and s.generation == generation and alive(s.player) == character
    end
    for index = 1, count do
        if not current() then return result(false, "Encounter cancelled") end
        local point = Arena.GroupPoint(origin, index, count, s.size, stage and stage.distance)
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
        if ready and (not stage or character:GetAttribute("AttackEndsAt")==nil) then
            if stage then
                Arena.Warp(character,origin)
                character:SetAttribute("GameplayGuideTrial",true)
                Report.Begin(s.player,character,models[1],stage)
                Report.Sample(0)
                s.guide.running=true
                publishGuide(s,("%d/%d · %s · Fight!"):format(#s.guide.results+1,#s.guide.stages,stage.label))
            end
            for _, model in ipairs(models) do
                model:SetAttribute("GameplayTestArmed", true)
                model:SetAttribute("MonsterAggressive", true)
            end
            return result(true, ("Group started: %d × %s LVL %d"):format(count, row.type, row.level))
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
    if action == "guideAbort" then
        clearGroup(s); s.guide=nil; publishGuide(s,"Guided test cancelled"); return result(true,"Guided test cancelled")
    end
    if action == "guideBegin" then
        if s.guide then return result(false,"Guided test already exists") end
        clearGroup(s)
        s.guide={stages=Plan.Build(),results={},running=false}
        publishGuide(s,("0/%d · Next to start"):format(#s.guide.stages))
        return result(true,"Guided test ready")
    end
    if action == "guideNext" then
        local g=s.guide
        if not g or g.running then return result(false,"Finish current trial first") end
        local stage=g.stages[#g.results+1]
        if not stage then return result(false,"All trials complete · Done") end
        local selection,reason=Loadout.Validate(stage)
        if not selection then return result(false,tostring(reason)) end
        local applied=apply(s,selection)
        if not applied.ok then return applied end
        local metadata=table.clone(stage); metadata.visualPlaceholder=selection.placeholder
        return startGroup(s,assert(Balance.Monster(stage.monsterId)),1,metadata)
    end
    if action == "guideDone" then
        local g=s.guide
        if not g or g.running or #g.results~=#g.stages then return result(false,"Complete all trials first") end
        Report.Emit(g.results,RuntimeVersion.Version)
        s.guide=nil; publishGuide(s,"Report exported · copy GP_REPORT from Output")
        return result(true,"Report exported to server Output")
    end
    if s.guide then return result(false,"Guided test active · use Next / Done / Cancel") end
    if action == "recovery" then
        local character = alive(player)
        if not character then return result(false, "Respawn first") end
        local ok, reason = Loadout.SetRecovery(player, character, request.regen, request.vampiric)
        return result(ok, if ok then "Recovery settings applied" else tostring(reason))
    end
    if action == "stop" then clearGroup(s); return result(true, "Group cleared") end
    local monster = if type(request.monsterId) == "string" then Balance.Monster(request.monsterId) else nil
    if monster and not s.layout.slots[monster.id] then return result(false,"Monster not enabled on test stand") end
    if action == "apply" or action == "start" then
        local selection, reason = Loadout.Validate(request)
        if not selection then return result(false, tostring(reason)) end
        if action == "start" and (not monster or not validInt(request.count, Balance.Test.maxGroup)) then return result(false, "Invalid group") end
        local applied = apply(s, selection)
        if not applied.ok or action == "apply" then return applied end
        return startGroup(s, monster, request.count)
    end
    if action == "visit" and monster then
        local character = alive(player)
        if not character then return result(false, "Respawn first") end
        if character:GetAttribute("AttackEndsAt") ~= nil then return result(false, "Finish current attack first") end
        clearGroup(s)
        Arena.Warp(character, s.layout.slots[monster.id].visit)
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
