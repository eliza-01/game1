--!strict
local ContentProvider = game:GetService("ContentProvider")

local loaded: {[string]: boolean} = {}
local Preloader = {}

local function push(bucket: {[string]: boolean}, value: string?)
    if type(value) == "string" and value ~= "" then bucket[value] = true end
end

local function collect(model: Model): {string}
    local bucket: {[string]: boolean} = {}
    for _, object in ipairs(model:GetDescendants()) do
        if object:IsA("MeshPart") then
            push(bucket, object.MeshId)
            push(bucket, object.TextureID)
        elseif object:IsA("SurfaceAppearance") then
            push(bucket, object.ColorMap)
            push(bucket, object.MetalnessMap)
            push(bucket, object.NormalMap)
            push(bucket, object.RoughnessMap)
        elseif object:IsA("Decal") then
            push(bucket, object.Texture)
        elseif object:IsA("Texture") then
            push(bucket, object.Texture)
        elseif object:IsA("SpecialMesh") then
            push(bucket, object.MeshId)
            push(bucket, object.TextureId)
        end
    end
    local items = {}
    for id in pairs(bucket) do table.insert(items, id) end
    table.sort(items)
    return items
end

function Preloader.PreloadModel(model: Model, isCurrent: (() -> boolean)?, onProgress: ((number) -> ())?): boolean
    local queue = collect(model)
    local pending = {}
    for _, id in ipairs(queue) do
        if not loaded[id] then table.insert(pending, id) end
    end
    if onProgress then onProgress(if #pending == 0 then 1 else 0) end
    if #pending == 0 then return not isCurrent or isCurrent() end
    for index, id in ipairs(pending) do
        if isCurrent and not isCurrent() then return false end
        local ok, err = pcall(ContentProvider.PreloadAsync, ContentProvider, {id})
        if not ok then
            warn("[game1][character-creation] preload failed: " .. tostring(err))
        else
            loaded[id] = true
        end
        if onProgress then onProgress(index / #pending) end
    end
    return not isCurrent or isCurrent()
end

return table.freeze(Preloader)
