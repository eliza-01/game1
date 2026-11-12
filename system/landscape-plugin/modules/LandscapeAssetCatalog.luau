-- Read-only published Location Asset registry, exactly the same source and
-- the same validated published-Model loader as Game1Bridge / DecoManager.
-- No writes to the registry and no duplicate asset database.
local HttpService = game:GetService("HttpService")
local AssetService = game:GetService("AssetService")
local DecoAssetLoader = require(script.Parent.DecoAssetLoader)

local Catalog = {}
Catalog.__index = Catalog

local URL = "http://127.0.0.1:43821"
local TOKEN = "Game1LocalControlV1"

function Catalog.new()
    local loader = DecoAssetLoader.new({
        HttpService = HttpService, AssetService = AssetService,
        agentBaseUrl = URL, agentToken = TOKEN,
    })
    return setmetatable({loader = loader, rows = {}}, Catalog)
end

function Catalog:Refresh()
    local snapshot = self.loader:fetchRegistry()
    local rows = {}
    for _, row in ipairs(snapshot.items) do
        if type(row) == "table" and row.status == "PUBLISHED"
            and type(row.slug) == "string" and row.slug ~= ""
            and tonumber(row.model_asset_id) and tonumber(row.model_asset_id) > 0 then
            table.insert(rows, row)
        end
    end
    table.sort(rows, function(a, b)
        return a.slug:lower() < b.slug:lower()
    end)
    self.rows = rows
    return rows
end

function Catalog:Load(row)
    -- Uses the shared normalization/skin connection/texture binding policy.
    local model = self.loader:loadPublished(row)
    if model.Parent ~= nil then
        model:Destroy()
        error("published location model must be detached before authoring")
    end
    -- Authoring requires two independent copies: a disposable cursor ghost
    -- and an Undo-recorded placed Model. Asset import may mark individual
    -- instances as non-archivable; normalize only the detached local template.
    model.Archivable = true
    for _, descendant in ipairs(model:GetDescendants()) do
        descendant.Archivable = true
    end
    return model
end

return Catalog
