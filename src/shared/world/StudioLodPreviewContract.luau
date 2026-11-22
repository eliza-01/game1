-- Studio-only transport contract; compiled runtime manifest is independent.
local HttpService = game:GetService("HttpService")
local Policy = require(script.Parent:WaitForChild("LocationLodDistancePolicy"))
local Contract = {Marker = "Game1StudioLodPreview", Cache = "Game1StudioLodTemplates"}
local function id(value)
    return type(value) == "string" and (value == "" or (value:match("^[1-9]%d*$") ~= nil
        and #value <= 16 and tonumber(value) < 9007199254740992))
end
function Contract.Read(marker)
    if not marker or not marker:IsA("StringValue") or #marker.Value >= 180000 then return nil end
    local ok, data = pcall(HttpService.JSONDecode, HttpService, marker.Value)
    if not ok or type(data) ~= "table" or data.schemaVersion ~= 2
        or not Policy.ValidHysteresis(data.hysteresis)
        or type(data.digest) ~= "string"
        or type(data.locations) ~= "table" or type(data.houses) ~= "table" then return nil end
    local ids = {}
    local function add(value)
        if value ~= "" then ids[value] = true end
    end
    for slug, row in pairs(data.locations) do
        if type(slug) ~= "string" or type(row) ~= "table" or not id(row.lod1) or not id(row.lod2)
            or not Policy.Valid(Policy.WithHysteresis(row.distances, data.hysteresis), row.mode)
            or not ({off=true, full=true, lod1=true, lod2=true})[row.mode] then return nil end
        if row.mode == "lod1" or row.mode == "lod2" then add(row.lod1) end
        if row.mode == "lod2" then add(row.lod2) end
    end
    for slug, row in pairs(data.houses) do
        if type(slug) ~= "string" or type(row) ~= "table" or type(row.parts) ~= "table"
            or not ({off=true, full=true, lod1=true})[row.mode] then return nil end
        for name, part in pairs(row.parts) do
            if type(name) ~= "string" or type(part) ~= "table" or not id(part.assetId)
                or type(part.lod1) ~= "number" or type(part.hide) ~= "number"
                or part.lod1 % 1 ~= 0 or part.hide % 1 ~= 0
                or part.lod1 < 20 or part.hide > 10000 or part.lod1 <= data.hysteresis or part.hide - part.lod1 <= math.max(20, 2 * data.hysteresis) then return nil end
            if row.mode == "lod1" then add(part.assetId) end
        end
    end
    local count = 0
    for _ in pairs(ids) do count += 1 end
    if count > 256 then return nil end
    return data, ids
end
return table.freeze(Contract)
