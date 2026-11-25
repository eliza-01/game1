--!strict
-- One slot per player for the current Character Creation milestone. Server-only.
-- Persistence is authoritative when DataStore is available; Studio may run session-only.
local DataStoreService = game:GetService("DataStoreService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Store = {}
Store.__index = Store
local records: {[Player]: any} = {}
local persistent: {[Player]: boolean} = {}
local committed: {[Player]: boolean} = {}
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
if not available then
    warn("[game1][character-profiles] DataStore unavailable: " .. tostring(database))
end

function Store.Load(player: Player): (any?, boolean)
    local ok, raw = pcall(function()
        if not available then error("DataStore unavailable") end
        return database:GetAsync("player_" .. tostring(player.UserId))
    end)
    if not ok then
        warn("[game1][character-profiles] read unavailable; session-only: " .. tostring(raw))
    end
    if player.Parent ~= Players then return nil, false end
    persistent[player] = ok
    if ok and raw ~= nil and (type(raw) ~= "table" or raw.schemaVersion ~= 1) then
        warn("[game1][character-profiles] unsupported stored schema; refusing migration-free load")
        persistent[player] = false
        return nil, false
    end
    if type(raw) == "table" and raw.schemaVersion == 1 and
        (raw.archetype == "human_male" or raw.archetype == "human_female") and type(raw.appearance) == "table" then
        records[player] = {schemaVersion = 1, archetype = raw.archetype,
            appearance = raw.appearance, lastWorldCFrame = raw.lastWorldCFrame}
    end
    committed[player] = records[player] ~= nil and ok
    return records[player], ok
end
function Store.Get(player: Player): any?
    return records[player]
end
-- Called only after authoritative appearance validation. Existing profiles are
-- canonicalized in session; the normal position/save path persists the upgrade.
function Store.SetValidatedAppearance(player: Player, appearance: any)
    local record = assert(records[player], "character profile is not loaded")
    record.appearance = appearance
end
local function writeRecord(player: Player, record: any, createOnly: boolean?): (boolean, any?)
    if persistent[player] ~= true then return false, nil end
    local occupied = false
    local existing = nil
    local ok, err = pcall(function()
        database:UpdateAsync("player_" .. tostring(player.UserId), function(previous)
            occupied = false
            existing = nil
            if createOnly and previous ~= nil then
                occupied = true
                existing = previous
                return nil -- Never overwrite a character created by a concurrent session.
            end
            return record
        end)
    end)
    if not ok or occupied then
        warn("[game1][character-profiles] write refused: " .. tostring(if occupied then "slot already exists" else err))
    end
    return ok and not occupied, if ok and occupied then existing else nil
end
function Store.Save(player: Player): boolean
    local record = records[player]
    if not record then return false end
    local saved = writeRecord(player, record, false)
    if saved then committed[player] = true end
    return saved
end
function Store.Create(player: Player, archetype: string, appearance: any): (boolean, boolean)
    if records[player] then return true, committed[player] == true end
    local candidate = {schemaVersion = 1, archetype = archetype, appearance = appearance}
    local saved, existing = writeRecord(player, candidate, true)
    if player.Parent ~= Players then return false, false end
    if existing ~= nil then
        -- UpdateAsync observed an already committed slot (e.g. a lost response).
        -- Reuse the authoritative record, never the attempted local appearance.
        if type(existing) == "table" and existing.schemaVersion == 1
            and (existing.archetype == "human_male" or existing.archetype == "human_female")
            and type(existing.appearance) == "table" then
            records[player] = existing
            committed[player] = true
            return true, true
        end
        records[player] = nil
        return false, false
    end
    if not saved and not RunService:IsStudio() then
        records[player] = nil
        return false, false
    end
    records[player] = candidate
    committed[player] = saved
    return true, saved
end
function Store.RememberPosition(player: Player, character: Model?): boolean
    if not records[player] or not character or character:GetAttribute("LifeState") ~= "Alive" then return false end
    local root = character:FindFirstChild("RootCollider")
    if root and root:IsA("BasePart") then
        local frame = safeFrame(root.CFrame)
        if frame then records[player].lastWorldCFrame = frame end
    end
    local saved = Store.Save(player)
    return saved
end
function Store.SpawnFrame(player: Player): CFrame?
    local record = records[player]
    return if record then decodeFrame(record.lastWorldCFrame) else nil
end
function Store.ForgetSession(player: Player)
    records[player] = nil
    persistent[player] = nil
    committed[player] = nil
end
return table.freeze(Store)
