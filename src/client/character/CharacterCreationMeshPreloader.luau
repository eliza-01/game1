--!strict
-- ContentProvider needs typed instances: a bare mesh URI is treated as an image.
local ContentProvider = game:GetService("ContentProvider")

type Item = {key: string, id: string, geometry: boolean, source: Instance?}
local loaded: {[string]: boolean} = {}
local inFlight: {[string]: any} = {}
local failedUntil: {[string]: number} = {}
local lastWarning: {[string]: number} = {}
local activeCount = 0
local MAX_CONCURRENT = 4
local Preloader = {}

local function push(bucket: {[string]: Item}, value: string?, geometry: boolean, source: Instance?)
    if type(value) ~= "string" or value == "" or value == "rbxassetid://0" then return end
    local key = (if geometry then "mesh:" else "image:") .. value
    if not bucket[key] then bucket[key] = {key = key, id = value, geometry = geometry, source = source} end
end

local function collect(model: Model): {Item}
    local bucket: {[string]: Item} = {}
    for _, object in ipairs(model:GetDescendants()) do
        if object:IsA("MeshPart") then
            push(bucket, object.MeshId, true, object)
            push(bucket, object.TextureID, false, nil)
        elseif object:IsA("Decal") or object:IsA("Texture") then
            push(bucket, object.Texture, false, nil)
        elseif object:IsA("SpecialMesh") then
            if object.MeshType == Enum.MeshType.FileMesh then push(bucket, object.MeshId, true, object) end
            push(bucket, object.TextureId, false, nil)
        end
        -- SurfaceAppearance uses engine-processed texture packs, not raw map
        -- requests; ContentProvider does not support preloading these packs.
    end
    local items: {Item} = {}
    for _, item in pairs(bucket) do table.insert(items, item) end
    table.sort(items, function(a, b)
        if a.geometry ~= b.geometry then return a.geometry end
        return a.key < b.key
    end)
    return items
end

-- Isolate geometry from texture failure, and own the instance until the async
-- request finishes (the requesting preview may be cancelled/destroyed meanwhile).
local function typedRequest(item: Item): Instance
    if not item.geometry then
        local decal = Instance.new("Decal")
        decal.Texture = item.id
        return decal
    end
    local source = item.source
    assert(source, "missing geometry source")
    if source:IsA("MeshPart") then
        local copy = source:Clone()
        assert(copy, "mesh is not archivable")
        copy:ClearAllChildren()
        copy.TextureID = ""
        return copy
    end
    assert(source:IsA("SpecialMesh"), "unsupported mesh source")
    local mesh = Instance.new("SpecialMesh")
    mesh.MeshType = Enum.MeshType.FileMesh
    mesh.MeshId = item.id
    return mesh
end

-- Shared typed cache and bounded pool across prewarm, previews and world entry.
local function fetch(item: Item): any?
    local key = item.key
    if loaded[key] then return {done = true, success = true} end
    if inFlight[key] then return inFlight[key] end
    if (failedUntil[key] or 0) > os.clock() then return {done = true, success = false} end
    if activeCount >= MAX_CONCURRENT then return nil end
    local result: any = {done = false, success = false}
    inFlight[key] = result
    activeCount += 1
    task.spawn(function()
        local request: Instance? = nil
        local callbackSeen, success = false, true
        local failureStatus: string? = nil
        local ok, err = pcall(function()
            request = typedRequest(item)
            ContentProvider:PreloadAsync({request}, function(_, status)
                callbackSeen = true
                success = success and status == Enum.AssetFetchStatus.Success
                if status ~= Enum.AssetFetchStatus.Success then failureStatus = tostring(status) end
            end)
        end)
        if request then request:Destroy() end
        if ok and callbackSeen and success then
            loaded[key] = true
            failedUntil[key] = nil
            result.success = true
        else
            failedUntil[key] = os.clock() + 2
            local now = os.clock()
            if not lastWarning[key] or now - lastWarning[key] >= 15 then
                lastWarning[key] = now
                local reason = if not ok then tostring(err) else failureStatus or "no fetch callback"
                warn("[game1][character-creation] typed asset fetch failed: " .. key .. " · " .. reason)
            end
        end
        result.done = true
        inFlight[key] = nil
        activeCount -= 1
    end)
    return result
end

function Preloader.PreloadModel(model: Model, isCurrent: (() -> boolean)?, onProgress: ((number) -> ())?): (boolean, boolean)
    local queue = collect(model)
    local jobs: {[string]: any} = {}
    local deadline = os.clock() + 25
    local function current(): boolean return not isCurrent or isCurrent() end
    local completed, successful, geometryReady = 0, 0, true
    repeat
        if not current() then return false, false end
        completed, successful, geometryReady = 0, 0, true
        for _, item in ipairs(queue) do
            local job = jobs[item.key]
            if not job then
                job = fetch(item)
                jobs[item.key] = job
            end
            if job and job.done then completed += 1 end
            if job and job.done and job.success then successful += 1
            elseif item.geometry then geometryReady = false end
        end
        if onProgress then onProgress(if #queue == 0 then 1 else successful / #queue) end
        if completed == #queue or os.clock() >= deadline then break end
        task.wait(0.05)
    until false
    return successful == #queue and current(), geometryReady and current()
end

return table.freeze(Preloader)
