--!strict
-- Explicit player lifecycle: creation -> selection -> gameplay. Never spawn on join.
local Players = game:GetService("Players")
local Gateway = {}
Gateway.__index = Gateway

function Gateway.new(enabled: boolean, available: (string) -> boolean,
    spawn: (Player, string, any?, CFrame?) -> Model?,
    validate: (string, any, boolean?) -> (any?, string?), profiles: any, dismiss: (Player) -> ()): any
    return setmetatable({enabled = enabled, available = available, spawn = spawn,
        validate = validate, profiles = profiles, dismiss = dismiss,
        busy = {} :: {[Player]: boolean}, pending = {} :: {[Player]: boolean}, nextRequest = {} :: {[Player]: number}}, Gateway)
end
function Gateway:Stage(player: Player, stage: string)
    self.pending[player] = true
    player:SetAttribute("CharacterCreationStatus", stage)
    player:SetAttribute("CharacterCreationPending", true)
end
function Gateway:Request(player: Player, operation: () -> any): any
    if self.busy[player] then return {ok = false, error = "request_in_progress"} end
    self.busy[player] = true
    local ok, result = pcall(operation)
    self.busy[player] = nil
    if not ok then
        warn("[game1][character-creation] lifecycle request failed: " .. tostring(result))
        return {ok = false, error = "request_failed"}
    end
    return result
end
function Gateway:Bind(remotes: Folder)
    local create = remotes:FindFirstChild("CharacterCreationSelect") or Instance.new("RemoteFunction")
    assert(create:IsA("RemoteFunction"), "CharacterCreationSelect must be RemoteFunction")
    create.Name = "CharacterCreationSelect"
    create.Parent = remotes
    create.OnServerInvoke = function(player: Player, archetypeId: any, appearance: any)
        return self:Request(player, function()
            if not self.enabled or not self.pending[player] then
                return {ok = false, error = "creation_not_pending"}
            end
            local stage = player:GetAttribute("CharacterCreationStatus")
            local existing = self.profiles.Get(player)
            if stage == "selection" and existing then
                -- A retry after commit must acknowledge the existing character,
                -- never create a second one or overwrite its appearance.
                local checked, problem = self.validate(existing.archetype, existing.appearance, true)
                if not checked then return {ok = false, error = problem or "saved_appearance_invalid"} end
                self.profiles.SetValidatedAppearance(player, checked)
                return {ok = true, mode = "selection", archetype = existing.archetype,
                    appearance = checked, persisted = player:GetAttribute("CharacterProfilePersisted")}
            end
            if stage ~= "creation" then return {ok = false, error = "creation_not_pending"} end
            if archetypeId ~= "human_male" and archetypeId ~= "human_female" then
                return {ok = false, error = "invalid_archetype"}
            end
            if not self.available(archetypeId) then return {ok = false, error = "assembly_not_ready"} end
            if os.clock() < (self.nextRequest[player] or 0) then return {ok = false, error = "rate_limited"} end
            self.nextRequest[player] = os.clock() + 1.5
            local checked, problem = self.validate(archetypeId, appearance)
            if not checked then return {ok = false, error = problem or "invalid_appearance"} end
            local created, persisted = self.profiles.Create(player, archetypeId, checked)
            if not created then return {ok = false, error = "character_save_failed"} end
            local record = self.profiles.Get(player)
            if not record then return {ok = false, error = "character_save_failed"} end
            local savedAppearance, savedProblem = self.validate(record.archetype, record.appearance, true)
            if not savedAppearance then return {ok = false, error = savedProblem or "saved_appearance_invalid"} end
            self.profiles.SetValidatedAppearance(player, savedAppearance)
            player:SetAttribute("CharacterProfilePersisted", persisted)
            player:SetAttribute("CharacterProfileArchetype", record.archetype)
            self:Stage(player, "selection")
            self.nextRequest[player] = nil
            return {ok = true, archetype = record.archetype, appearance = savedAppearance,
                persisted = persisted, mode = "selection"}
        end)
    end
    local read = remotes:FindFirstChild("CharacterCreationRead") or Instance.new("RemoteFunction")
    assert(read:IsA("RemoteFunction"), "CharacterCreationRead must be RemoteFunction")
    read.Name = "CharacterCreationRead"
    read.Parent = remotes
    read.OnServerInvoke = function(player: Player)
        if not self.enabled or not self.pending[player] or player:GetAttribute("CharacterCreationStatus") ~= "selection" then
            return {ok = false, error = "selection_not_pending"}
        end
        local record = self.profiles.Get(player)
        if not record then return {ok = false, error = "character_unavailable"} end
        local checked, problem = self.validate(record.archetype, record.appearance, true)
        if not checked then return {ok = false, error = problem or "saved_appearance_invalid"} end
        self.profiles.SetValidatedAppearance(player, checked)
        return {ok = true, archetype = record.archetype, appearance = checked}
    end
    local enter = remotes:FindFirstChild("CharacterCreationEnter") or Instance.new("RemoteFunction")
    assert(enter:IsA("RemoteFunction"), "CharacterCreationEnter must be RemoteFunction")
    enter.Name = "CharacterCreationEnter"
    enter.Parent = remotes
    enter.OnServerInvoke = function(player: Player)
        return self:Request(player, function()
            if not self.enabled or not self.pending[player] or player:GetAttribute("CharacterCreationStatus") ~= "selection" then
                return {ok = false, error = "selection_not_pending"}
            end
            if os.clock() < (self.nextRequest[player] or 0) then return {ok = false, error = "rate_limited"} end
            self.nextRequest[player] = os.clock() + 1
            local record = self.profiles.Get(player)
            if not record or not self.available(record.archetype) then return {ok = false, error = "character_unavailable"} end
            local checked, problem = self.validate(record.archetype, record.appearance, true)
            if not checked then return {ok = false, error = problem or "saved_appearance_invalid"} end
            self.profiles.SetValidatedAppearance(player, checked)
            local model = self.spawn(player, record.archetype, checked, self.profiles.SpawnFrame(player))
            if not model then return {ok = false, error = "spawn_failed"} end
            self.pending[player] = nil
            player:SetAttribute("CharacterCreationPending", false)
            player:SetAttribute("CharacterCreationStatus", "world")
            return {ok = true}
        end)
    end
    local switch = remotes:FindFirstChild("CharacterCreationManage") or Instance.new("RemoteFunction")
    assert(switch:IsA("RemoteFunction"), "CharacterCreationManage must be RemoteFunction")
    switch.Name = "CharacterCreationManage"
    switch.Parent = remotes
    switch.OnServerInvoke = function(player: Player)
        return self:Request(player, function()
            if not self.enabled or self.pending[player] or player:GetAttribute("CharacterCreationStatus") ~= "world" then
                return {ok = false, error = "not_in_world"}
            end
            local record = self.profiles.Get(player)
            if not record then return {ok = false, error = "character_unavailable"} end
            local character = player.Character
            if not character or character:GetAttribute("LifeState") ~= "Alive"
                or character:GetAttribute("InCombat") == true
                or (tonumber(character:GetAttribute("CombatUntilServerTime")) or 0) > workspace:GetServerTimeNow() then
                return {ok = false, error = "cannot_switch_while_fighting"}
            end
            local saved = self.profiles.RememberPosition(player, character)
            if not saved and not game:GetService("RunService"):IsStudio() then
                return {ok = false, error = "position_save_failed"}
            end
            self:Stage(player, "selection")
            self.dismiss(player)
            self.nextRequest[player] = nil
            return {ok = true}
        end)
    end
end
function Gateway:Join(player: Player)
    if not self.enabled then
        player:SetAttribute("CharacterCreationPending", false)
        task.defer(self.spawn, player, "", nil, nil)
        return
    end
    -- Fail closed even while DataStore is yielding: no avatar appears during load.
    -- Defensive cleanup for Studio sessions where a default Roblox character
    -- may have been created before our earliest bootstrap hook ran.
    if player.Character then self.dismiss(player) end
    self:Stage(player, "loading")
    task.spawn(function()
        local record, persisted = self.profiles.Load(player)
        if player.Parent ~= Players or not self.pending[player] then return end
        if not persisted and not game:GetService("RunService"):IsStudio() then
            self:Stage(player, "storage_unavailable")
            player:SetAttribute("CharacterProfilePersisted", false)
            return
        end
        if record then
            self:Stage(player, "selection")
        else
            self:Stage(player, "creation")
        end
        player:SetAttribute("CharacterProfilePersisted", persisted)
        player:SetAttribute("CharacterProfileArchetype", if record then record.archetype else "")
    end)
end
function Gateway:Leave(player: Player)
    self.pending[player] = nil
    self.nextRequest[player] = nil
end
return Gateway
