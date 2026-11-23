--!strict
-- Shared pure contract: stable locale IDs and fallback policy, no player state.
local Catalog = require(script.Parent:WaitForChild("GameTextCatalog"))
local Contract = {}

function Contract.Normalize(value: any): string
    if typeof(value) ~= "string" then return Catalog.defaultLocale end
    local locale = string.lower(value):gsub("_", "-")
    if Catalog.locales[locale] then return locale end
    local language = string.match(locale, "^[a-z]+") or ""
    local primary = {
        ru = "ru-ru", en = "en-us", de = "de-de", zh = "zh-cn",
        it = "it-it", es = "es-es", fr = "fr-fr", pt = "pt-br",
        ja = "ja-jp", ko = "ko-kr",
    }
    return primary[language] or Catalog.defaultLocale
end

function Contract.IsSupported(value: any): boolean
    return typeof(value) == "string" and Catalog.locales[value] ~= nil
end

function Contract.Translate(locale: string, key: string, params: {[string]: any}?): string
    local groupName = string.match(key, "^([a-z]+)%.")
    local row = groupName and Catalog.groups[groupName] and Catalog.groups[groupName][key]
    if not row then return key end
    local text = row.translations[Contract.Normalize(locale)] or row.translations[Catalog.defaultLocale] or row.source
    if not params then return text end
    return (string.gsub(text, "{([%a_][%w_]*)}", function(name)
        local value = params[name]
        return if value ~= nil then tostring(value) else "{" .. name .. "}"
    end))
end

return table.freeze(Contract)
