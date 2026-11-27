--!strict
-- Pure persistence contract. Slot IDs are stable; the ordered list is not identity.
local Roster = {}
Roster.Limit = 5

function Roster.Copy(value: any): any
    if type(value) ~= "table" then return value end
    local copy = {}
    for k, v in pairs(value) do copy[k] = Roster.Copy(v) end
    return copy
end

function Roster.Equal(a: any, b: any): boolean
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for k, v in pairs(a) do if not Roster.Equal(v, b[k]) then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end

local function valid(record: any): boolean
    return type(record) == "table" and (record.archetype == "human_male" or record.archetype == "human_female")
        and type(record.appearance) == "table"
end

function Roster.Find(document: any, id: any): (any?, number?)
    if type(id) ~= "string" or not document then return nil, nil end
    for i, record in ipairs(document.characters) do
        if record.id == id then return record, i end
    end
    return nil, nil
end

function Roster.Decode(raw: any): any?
    if raw == nil then return {schemaVersion = 2, characters = {}} end
    if type(raw) ~= "table" then return nil end
    if raw.schemaVersion == 1 and valid(raw) then
        local character = Roster.Copy(raw)
        character.schemaVersion = nil
        character.id = "legacy"
        return {schemaVersion = 2, characters = {character}, selectedId = character.id}
    end
    if raw.schemaVersion ~= 2 or type(raw.revision) ~= "string" or type(raw.characters) ~= "table"
        or #raw.characters > Roster.Limit then return nil end
    local ids = {}
    local count = 0
    for i, character in pairs(raw.characters) do
        if type(i) ~= "number" or i % 1 ~= 0 or i < 1 or i > #raw.characters or not valid(character)
            or type(character.id) ~= "string" or character.id == "" or ids[character.id] then return nil end
        ids[character.id] = true
        count = count + 1
    end
    if count ~= #raw.characters or (raw.selectedId ~= nil and not ids[raw.selectedId]) then return nil end
    local document = Roster.Copy(raw)
    document.selectedId = document.selectedId or (document.characters[1] and document.characters[1].id)
    return document
end

function Roster.Matches(previous: any, expected: any): boolean
    -- A pre-migration v1 writer has no revision, so compare the complete record.
    if type(expected) == "table" and expected.schemaVersion == 2 then
        return type(previous) == "table" and previous.schemaVersion == 2 and previous.revision == expected.revision
    end
    return Roster.Equal(previous, expected)
end

function Roster.Append(document: any, id: string, archetype: string, appearance: any): any?
    if #document.characters >= Roster.Limit or Roster.Find(document, id) then return nil end
    local candidate = Roster.Copy(document)
    table.insert(candidate.characters, {id = id, archetype = archetype, appearance = Roster.Copy(appearance), xp = 0, gold = 0})
    candidate.selectedId = id
    return candidate
end

function Roster.Remove(document: any, id: string): any?
    local _, index = Roster.Find(document, id)
    if not index then return nil end
    local candidate = Roster.Copy(document)
    table.remove(candidate.characters, index)
    local nextRecord = candidate.characters[math.min(index, #candidate.characters)]
    if candidate.selectedId == id then candidate.selectedId = nextRecord and nextRecord.id or nil end
    return candidate
end
return table.freeze(Roster)
