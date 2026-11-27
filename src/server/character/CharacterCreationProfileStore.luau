--!strict
-- Account roster persistence. All writes compare the last observed revision;
-- a stale server cannot overwrite a newer roster or resurrect a deleted slot.
local DataStoreService = game:GetService("DataStoreService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local HttpService = game:GetService("HttpService")
local Balance = require(game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared"):WaitForChild("balance"):WaitForChild("Balance"))
local Roster = require(script.Parent:WaitForChild("CharacterProfileRoster"))
local Store = {Limit = Roster.Limit}
local sessions: {[Player]: any} = {}
local function safeFrame(frame: any): {number}?
    if typeof(frame) ~= "CFrame" then return nil end
    local values = {frame:GetComponents()}
    for _, n in ipairs(values) do
        if type(n) ~= "number" or n ~= n or math.abs(n) > 100000 then return nil end
    end
    return values
end
local function decodeFrame(values: any): CFrame?
    if type(values) ~= "table" or #values ~= 12 then return nil end
    for _, n in ipairs(values) do
        if type(n) ~= "number" or n ~= n or math.abs(n) > 100000 then return nil end
    end
    return CFrame.new(table.unpack(values))
end
local available, database = pcall(function()
    return DataStoreService:GetDataStore("game1_character_profiles_v1")
end)
if not available then warn("[game1][character-profiles] DataStore unavailable: " .. tostring(database)) end
local function key(player: Player): string return "player_" .. tostring(player.UserId) end

function Store.Load(player: Player): (any?, boolean, boolean)
    local ok, raw = pcall(function()
        if not available then error("DataStore unavailable") end
        return database:GetAsync(key(player))
    end)
    if player.Parent ~= Players then return nil, false, false end
    if not ok then warn("[game1][character-profiles] read unavailable: " .. tostring(raw)) end
    local document = Roster.Decode(if ok then raw else nil)
    if not document or (not ok and not RunService:IsStudio()) then
        warn("[game1][character-profiles] load refused; persistent roster unavailable")
        return nil, false, false
    end
    for _, record in ipairs(document.characters) do
        record.xp = Balance.NormalizeXP(record.xp)
        record.gold = Balance.NormalizeGold(record.gold)
    end
    sessions[player] = {document = document, expected = if ok then raw else nil, persistent = ok, busy = false}
    return Store.Get(player), ok, true
end

function Store.Ready(player: Player): boolean
    local session = sessions[player]
    return session ~= nil and not session.blocked and not session.busy
end

function Store.Get(player: Player): any?
    local session = sessions[player]
    if not session then return nil end
    local record = Roster.Find(session.document, session.document.selectedId)
    return record
end

function Store.List(player: Player): ({any}, string?, boolean)
    local session = sessions[player]
    if not session then return {}, nil, false end
    local list = {}
    for _, record in ipairs(session.document.characters) do
        table.insert(list, {id = record.id, archetype = record.archetype, level = Balance.LevelForXP(record.xp)})
    end
    return list, session.document.selectedId, session.persistent
end

function Store.Select(player: Player, id: string): boolean
    local session = sessions[player]
    if not session or session.busy or session.blocked or not Roster.Find(session.document, id) then return false end
    session.document.selectedId = id
    return true
end

function Store.SetValidatedAppearance(player: Player, appearance: any)
    local record = assert(Store.Get(player), "character profile is not loaded")
    record.appearance = appearance
end

local function commit(player: Player, session: any, candidate: any, replace: boolean): boolean
    if session.busy or session.blocked then return false end
    if not session.persistent then
        if not RunService:IsStudio() then return false end
        if replace then session.document = candidate end
        return true
    end
    session.busy = true
    candidate.revision = HttpService:GenerateGUID(false)
    local saved = false
    local conflict = false
    local lastError: any = nil
    -- Retry an ambiguous transport result using the SAME revision. If the first
    -- write actually committed, acknowledge it rather than append/delete twice.
    for _ = 1, 2 do
        local ok, result = pcall(function()
            return database:UpdateAsync(key(player), function(previous)
                if type(previous) == "table" and previous.schemaVersion == 2 and previous.revision == candidate.revision then
                    return previous
                end
                if not Roster.Matches(previous, session.expected) then return nil end
                return candidate
            end)
        end)
        if ok then
            saved = type(result) == "table" and result.revision == candidate.revision
            conflict = not saved
            break
        end
        lastError = result
    end
    session.busy = false
    if not saved then
        -- Fail closed after a conflict/uncertain commit. Rejoin to reload the
        -- authoritative document; never continue writing a stale local copy.
        session.blocked = true
        warn("[game1][character-profiles] write refused: " .. tostring(if conflict then "revision_conflict" else lastError))
        return false
    end
    session.expected = Roster.Copy(candidate)
    if replace then session.document = candidate else session.document.revision = candidate.revision end
    return true
end

function Store.Save(player: Player): boolean
    local session = sessions[player]
    if not session or not Store.Get(player) then return false end
    return commit(player, session, Roster.Copy(session.document), false)
end

function Store.Create(player: Player, archetype: string, appearance: any): (boolean, boolean)
    local session = sessions[player]
    if not session then return false, false end
    local candidate = Roster.Append(session.document, HttpService:GenerateGUID(false), archetype, appearance)
    if not candidate or not commit(player, session, candidate, true) then return false, false end
    if player.Parent ~= Players or sessions[player] ~= session then return false, false end
    return true, session.persistent
end

function Store.Delete(player: Player, id: string): boolean
    local session = sessions[player]
    if not session or session.document.selectedId ~= id then return false end
    local candidate = Roster.Remove(session.document, id)
    if not candidate or not commit(player, session, candidate, true) then return false end
    return player.Parent == Players and sessions[player] == session
end

function Store.RememberPosition(player: Player, character: Model?): boolean
    local record = Store.Get(player)
    if not record then return false end
    if character and character:GetAttribute("Game1GameplayTestOwner") == nil and character:GetAttribute("LifeState") == "Alive" then
        local root = character:FindFirstChild("RootCollider")
        if root and root:IsA("BasePart") then
            local frame = safeFrame(root.CFrame)
            if frame then record.lastWorldCFrame = frame end
        end
    end
    return Store.Save(player)
end
function Store.SpawnFrame(player: Player): CFrame?
    local record = Store.Get(player)
    return if record then decodeFrame(record.lastWorldCFrame) else nil
end
function Store.ForgetSession(player: Player) sessions[player] = nil end
return table.freeze(Store)
