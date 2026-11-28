-- Versioned authoring contract. No vertex reads, no attack-time work.
-- The migration uses the same Roblox-imported geometry oracle as Runtime.
local HttpService = game:GetService("HttpService")
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local HeadResolver = require(ReplicatedStorage.Game1Shared.combat.SkeletonHeadResolver)
local registryOk, Registry = pcall(require, script.Parent:WaitForChild("HitboxAssetRegistry"))
local Definitions = {}
local VERSION = 1
local CAPTURE_LIMIT = 256
local captures, warned = {}, {}
local captureEnabled = RunService:IsStudio() and game:GetService("Workspace"):GetAttribute("Game1HitboxCapture") == true
local capturedCount = 0
local byKey = {}

local function path(instance, root)
    local names = {}
    while instance and instance ~= root do
        table.insert(names, 1, instance.Name)
        instance = instance.Parent
    end
    return names
end

local function vector(v)
    return {v.X, v.Y, v.Z}
end

-- Quantize root-relative frames, not absolute position or world yaw. A
-- different assembly/pose is a cache miss, never a guessed scaled box.
local function frame(cf)
    local values = {cf:GetComponents()}
    for i, value in ipairs(values) do
        local rounded = math.round(value * 10000)
        values[i] = rounded == 0 and 0 or rounded
    end
    return values
end

local function boneMapping(mapping, root)
    local rows = {}
    for name, bone in pairs(mapping) do
        table.insert(rows, {name, path(bone, root)})
    end
    table.sort(rows, function(a, b) return a[1] < b[1] end)
    return rows
end

local function signature(binding)
    local basis = binding.root.CFrame
    local parts, seen = {}, {}
    for _, record in ipairs(binding.records) do
        -- Non-published or ambiguous identities cannot be persisted safely.
        if not string.match(record.geometryKey, "^rbxassetid://%d+$") or seen[record.path] then
            return nil
        end
        seen[record.path] = true
        table.insert(parts, {path(record.meshPart, binding.visual), record.geometryKey,
            frame(basis:ToObjectSpace(record.meshPart.CFrame)), frame(CFrame.new(record.scale)),
            boneMapping(record.bonesByName, binding.visual)})
    end
    local bones, bonePaths = {}, {}
    for _, bone in ipairs(binding.visual:GetDescendants()) do
        if bone:IsA("Bone") then
            local namePath = path(bone, binding.visual)
            local encoded = HttpService:JSONEncode(namePath)
            if bonePaths[encoded] then return nil end
            bonePaths[encoded] = true
            table.insert(bones, {encoded, frame(basis:ToObjectSpace(HeadResolver.TransformedBoneFrame(bone)))})
        end
    end
    table.sort(bones, function(a, b) return a[1] < b[1] end)
    return HttpService:JSONEncode({parts, bones, binding.headBone and path(binding.headBone, binding.visual) or {},
        binding.headParentBone and path(binding.headParentBone, binding.visual) or {},
        boneMapping(binding.bonesByName, binding.visual)})
end

local function finite(x)
    return type(x) == "number" and x == x and math.abs(x) < math.huge
end

local function readVector(v, positive)
    if type(v) ~= "table" or #v ~= 3 then return nil end
    for _, n in ipairs(v) do
        if not finite(n) or (positive and n <= 0) then return nil end
    end
    return Vector3.new(v[1], v[2], v[3])
end

local function decodeBox(row, binding, head)
    if type(row) ~= "table" then return nil end
    local center, size = readVector(row.center, false), readVector(row.size, true)
    if not center or not size then return nil end
    if head then
        if row.kind ~= "head" or not binding.headBone or not binding.headParentBone
            or row.boneName ~= binding.headBone.Name then return nil end
    else
        if row.kind ~= "mesh" and row.kind ~= "bone" then return nil end
        if not finite(row.recordIndex) or row.recordIndex % 1 ~= 0 then return nil end
        local record = binding.records[row.recordIndex]
        if not record then return nil end
        if row.kind == "bone" then
            if type(row.boneName) ~= "string" then return nil end
            local bone = record.bonesByName[row.boneName] or binding.bonesByName[row.boneName]
            if not bone or not bone.Parent then return nil end
        end
    end
    return {kind = row.kind, recordIndex = row.recordIndex, boneName = row.boneName,
        localCFrame = CFrame.new(center), size = size}
end

local function decode(row, binding)
    if type(row) ~= "table" or not finite(row.broadRadius) or row.broadRadius <= 0
        or not finite(row.sourceVertexCount) or row.sourceVertexCount < 1 or row.sourceVertexCount % 1 ~= 0
        or type(row.bodyBoxes) ~= "table" then return nil end
    local result = {broadRadius = row.broadRadius, sourceVertexCount = row.sourceVertexCount, bodyBoxes = {}}
    for _, box in ipairs(row.bodyBoxes) do
        local decoded = decodeBox(box, binding, false)
        if not decoded then return nil end
        table.insert(result.bodyBoxes, decoded)
    end
    if row.headBox ~= nil then
        result.headBox = decodeBox(row.headBox, binding, true)
        if not result.headBox then return nil end
    end
    if #result.bodyBoxes == 0 and not result.headBox then return nil end
    return result
end

if registryOk and type(Registry) == "table" and Registry.schemaVersion == VERSION and type(Registry.entries) == "table" then
    for _, row in ipairs(Registry.entries) do
        if type(row) == "table" and type(row.key) == "string" and type(row.signature) == "string" then
            local bucket = byKey[row.key] or {}
            byKey[row.key] = bucket
            if bucket[row.signature] ~= nil then
                bucket[row.signature] = false -- ambiguous authoring data must not win
            else
                bucket[row.signature] = row.definition or false
            end
        else
            warn("[game1][hitbox-assets] malformed registry entry; ignored")
        end
    end
else
    warn("[game1][hitbox-assets] incompatible registry schema; migration oracle retained")
end

function Definitions.Lookup(binding, key)
    local bucket = byKey[key]
    if not bucket then
        if next(byKey) and not warned[key] then
            warned[key] = true
            warn("[game1][hitbox-assets] uncaptured mesh/rig/scale; using migration oracle: " .. key)
        end
        return nil
    end
    local ok, definition = pcall(function()
        local sig = signature(binding)
        return sig and decode(bucket[sig], binding)
    end)
    if not ok then definition = nil end
    if not definition and not warned[key] then
        warned[key] = true
        warn("[game1][hitbox-assets] revision/pose/bounds mismatch; using migration oracle: " .. key)
    end
    return definition
end

function Definitions.SetCaptureEnabled(enabled)
    assert(RunService:IsStudio(), "hitbox authoring is Studio-only")
    captureEnabled = enabled == true
end

function Definitions.CaptureSignature(binding)
    if not captureEnabled or capturedCount >= CAPTURE_LIMIT then return nil end
    local ok, result = pcall(signature, binding)
    if not ok then
        warn("[game1][hitbox-assets] capture signature failed: " .. tostring(result))
        return nil
    end
    return result
end

local function encodeBox(box)
    return {kind = box.kind, recordIndex = box.recordIndex, boneName = box.boneName,
        center = vector(box.localCFrame.Position), size = vector(box.size)}
end

function Definitions.Record(key, sig, definition)
    if not captureEnabled or capturedCount >= CAPTURE_LIMIT then return end
    local id = HttpService:JSONEncode({key, sig})
    if captures[id] then return end
    local body = {}
    for _, box in ipairs(definition.bodyBoxes) do table.insert(body, encodeBox(box)) end
    captures[id] = {key = key, signature = sig, definition = {
        broadRadius = definition.broadRadius, sourceVertexCount = definition.sourceVertexCount,
        bodyBoxes = body, headBox = definition.headBox and encodeBox(definition.headBox) or nil}}
    capturedCount += 1
end

function Definitions.ExportCaptured()
    assert(RunService:IsStudio(), "hitbox authoring is Studio-only")
    local entries = {}
    for _, row in pairs(captures) do table.insert(entries, row) end
    table.sort(entries, function(a, b)
        if a.key == b.key then return a.signature < b.signature end
        return a.key < b.key
    end)
    return {schemaVersion = VERSION, entries = entries}
end

return table.freeze(Definitions)
