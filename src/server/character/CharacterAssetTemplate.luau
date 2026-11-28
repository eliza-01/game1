-- Shared publication normalization; cache and instance lifetime belong to caller.
local InsertService = game:GetService("InsertService")
local Template = {}
function Template.Load(assetId: number): Model?
    local ok, bundle = pcall(InsertService.LoadAsset, InsertService, assetId)
    if not ok or not bundle then
        warn("[game1] cannot load character asset", assetId, bundle)
        return nil
    end

    local imported: Instance = bundle
    local children = bundle:GetChildren()
    if bundle:IsA("Model") and #children == 1 then
        imported = children[1]
        imported.Parent = nil
        bundle:Destroy()
    end

    local template: Model
    if imported:IsA("Model") then
        template = imported
    else
        template = Instance.new("Model")
        imported.Parent = template
    end
    return template
end
return table.freeze(Template)
