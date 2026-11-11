-- Plugin-local placement authoring presets. No new asset catalog or server DB.
-- Only one Use profile may be active; Apply is explicit and never automatic.
local Profiles = {}
Profiles.__index = Profiles

local KEY = "Game1LandscapeProfilesV1"
local MAX_PROFILES = 60
local MAX_NAME = 50

local function finite(value, minValue, maxValue): boolean
    return type(value) == "number" and value == value and value ~= math.huge
        and value ~= -math.huge and value >= minValue and value <= maxValue
end

function Profiles.Validate(settings)
    assert(type(settings) == "table", "profile settings missing")
    for _, axis in ipairs({"yaw", "pitch", "roll"}) do
        assert(finite(settings[axis], -360, 360), axis .. " must be -360..360")
    end
    assert(type(settings.tetherEnabled) == "boolean", "tetherEnabled must be boolean")
    assert(finite(settings.length, 0.05, 100), "tether length must be 0.05..100")
    assert(finite(settings.thickness, 0.02, 4), "tether thickness must be 0.02..4")
    assert(type(settings.color) == "string" and settings.color:match("^#%x%x%x%x%x%x$") ~= nil,
        "tether color must be #RRGGBB")
    return {
        yaw = settings.yaw, pitch = settings.pitch, roll = settings.roll,
        tetherEnabled = settings.tetherEnabled, length = settings.length,
        thickness = settings.thickness, color = settings.color:upper(),
    }
end

local function cleaned(data)
    local records = {}
    if type(data) == "table" and type(data.profiles) == "table" then
        for _, item in ipairs(data.profiles) do
            if #records >= MAX_PROFILES then break end
            if type(item) == "table" and type(item.name) == "string"
                and #item.name > 0 and #item.name <= MAX_NAME
                and type(item.id) == "string" and item.id:match("^[%w%-]+$") then
                local ok, settings = pcall(Profiles.Validate, item)
                if ok then
                    settings.id = item.id
                    settings.name = item.name
                    table.insert(records, settings)
                end
            end
        end
    end
    local activeId = if type(data) == "table" then data.activeId else nil
    if type(activeId) ~= "string" then activeId = nil end
    local exists = false
    for _, row in ipairs(records) do
        if row.id == activeId then exists = true end
    end
    return {profiles = records, activeId = if exists then activeId else nil}
end

function Profiles.new(plugin, httpService)
    local raw = plugin:GetSetting(KEY)
    local self = setmetatable({plugin = plugin, http = httpService}, Profiles)
    self.data = cleaned(raw)
    return self
end

function Profiles:List()
    return self.data.profiles, self.data.activeId
end

function Profiles:Find(id)
    for _, row in ipairs(self.data.profiles) do
        if row.id == id then return row end
    end
    return nil
end

function Profiles:Save()
    self.plugin:SetSetting(KEY, self.data)
end

function Profiles:Create(name, settings)
    assert(type(name) == "string" and name:match("%S") and #name <= MAX_NAME,
        "имя профиля должно быть от 1 до 50 символов")
    if #self.data.profiles >= MAX_PROFILES then error("лимит профилей: " .. MAX_PROFILES) end
    local item = Profiles.Validate(settings)
    item.name = name
    item.id = self.http:GenerateGUID(false)
    table.insert(self.data.profiles, item)
    self:Save()
    return item
end

function Profiles:Use(id, enabled)
    if enabled then
        assert(self:Find(id), "выбранного профиля больше нет")
        self.data.activeId = id
    elseif self.data.activeId == id then
        self.data.activeId = nil
    end
    self:Save()
end

function Profiles:Remove(id)
    for i, row in ipairs(self.data.profiles) do
        if row.id == id then
            table.remove(self.data.profiles, i)
            if self.data.activeId == id then self.data.activeId = nil end
            self:Save()
            return
        end
    end
    error("профиль не найден")
end

return Profiles
