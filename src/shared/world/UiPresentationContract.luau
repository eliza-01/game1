--!strict
-- Runtime fallback and validation for the generated GameOptions UI profile.
-- The Control Center owns persisted values; this contract prevents a missing
-- older registry from breaking the world UI before first options migration.
local Contract = {}
Contract.Defaults = table.freeze({
    desktop = table.freeze({
        interaction = table.freeze({offsetXPx=0, offsetYPx=0, widthPx=272, fontPx=14}),
        status = table.freeze({offsetXPx=0, offsetYPx=0, titleFontPx=13, labelFontPx=12, timerFontPx=11}),
        notification = table.freeze({offsetXPx=0, offsetYPx=0, fontPx=13, paddingPx=5, durationSeconds=2.7}),
        resource = table.freeze({offsetXPx=0, offsetYPx=0, fontPx=18, paddingPx=5, risePx=34, durationSeconds=0.9}),
    }),
    mobile = table.freeze({
        interaction = table.freeze({offsetXPx=0, offsetYPx=0, widthPx=272, fontPx=14}),
        status = table.freeze({offsetXPx=0, offsetYPx=0, titleFontPx=13, labelFontPx=12, timerFontPx=11}),
        notification = table.freeze({offsetXPx=0, offsetYPx=0, fontPx=13, paddingPx=5, durationSeconds=2.7}),
        resource = table.freeze({offsetXPx=0, offsetYPx=0, fontPx=18, paddingPx=5, risePx=34, durationSeconds=0.9}),
    }),
})
Contract.Bounds = table.freeze({
    offsetXPx={-500,500}, offsetYPx={-500,500}, widthPx={180,450},
    fontPx={10,36}, titleFontPx={10,36}, labelFontPx={10,36}, timerFontPx={9,36},
    risePx={0,200}, paddingPx={0,24}, durationSeconds={0.2,15},
})
function Contract.Validate(device: any, data: any): {[string]: any}?
    if device ~= "desktop" and device ~= "mobile" or type(data) ~= "table" then return nil end
    local schema = Contract.Defaults[device]
    local checked = {}
    for group, fields in pairs(schema) do
        local groupData = data[group]
        if type(groupData) ~= "table" then return nil end
        checked[group] = {}
        for name in pairs(fields) do
            local value = groupData[name]
            local bounds = Contract.Bounds[name]
            if type(value) ~= "number" or value ~= value or value == math.huge
                or value == -math.huge or not bounds or value < bounds[1] or value > bounds[2] then return nil end
            if name ~= "durationSeconds" and value % 1 ~= 0 then return nil end
            checked[group][name] = value
        end
        for name in pairs(groupData) do if fields[name] == nil then return nil end end
    end
    for group in pairs(data) do if schema[group] == nil then return nil end end
    return checked
end
return table.freeze(Contract)
