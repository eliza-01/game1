-- Versioned authoring contract. No vertex reads, no attack-time work.
-- The migration uses the same Roblox-imported geometry oracle as Runtime.
local HttpService = game:GetService("HttpService")
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local HeadResolver = require(ReplicatedStorage.Game1Shared.combat.SkeletonHeadResolver)
local registryOk, Registry = pcall(require, script.Parent:WaitForChild("HitboxAssetRegistry"))
local Definitions = {}
local VERSION = 2
local CAPTURE_LIMIT = 256
local captures, warned, accepted = {}, {}, {}
local captureEnabled = RunService:IsStudio() and game:GetService("Workspace"):GetAttribute("Game1HitboxCapture") == true
local capturedCount = 0
local byKey = {}
local sessionByKey = {}
local sessionCount = 0
local SESSION_LIMIT = 256
-- One quantization unit is 0.0001 studs / matrix coefficient. Allow two
-- units for world-coordinate float cancellation, not a different pose.
local FRAME_TOLERANCE = 2

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

local function signature(binding, componentNames)
    local basis = binding.records[1].meshPart.CFrame
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
    local candidates = binding.visual:GetDescendants()
    local mapping = binding.bonesByName
    if componentNames then
        candidates, mapping = {}, {}
        local included = {}
        local function add(bone)
            if bone and not included[bone] then
                included[bone] = true
                table.insert(candidates, bone)
            end
        end
        for _, name in ipairs(componentNames) do
            local bone = binding.records[1].bonesByName[name] or binding.bonesByName[name]
            if not bone or not bone.Parent then return nil end
            mapping[name] = bone
            add(bone)
        end
        add(binding.headBone)
        add(binding.headParentBone)
    end
    for _, bone in ipairs(candidates) do
        if bone:IsA("Bone") then
            local namePath = path(bone, binding.visual)
            local encoded = HttpService:JSONEncode(namePath)
            if bonePaths[encoded] then return nil end
            bonePaths[encoded] = true
            table.insert(bones, {encoded, frame(basis:ToObjectSpace(HeadResolver.TransformedBoneFrame(bone)))})
        end
    end
    table.sort(bones, function(a, b) return a[1] < b[1] end)
    -- The exact oracle uses the root center (broad radius) and its up axis
    -- (head split), not the root AABB dimensions or horizontal axes.
    local rootCenter = basis:PointToObjectSpace(binding.root.Position)
    local rootUp = basis:VectorToObjectSpace(binding.root.CFrame.UpVector)
    return {parts, bones, binding.headBone and path(binding.headBone, binding.visual) or {},
        binding.headParentBone and path(binding.headParentBone, binding.visual) or {},
        boneMapping(mapping, binding.visual), {frame(CFrame.new(rootCenter)), frame(CFrame.new(rootUp))}}
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

-- Compare the decoded contract structurally, independent of JSON whitespace
-- and empty array encoding. Numeric tolerance is restricted to spatial frames.
local function same(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for k, v in pairs(a) do if not same(v, b[k]) then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end

local function nearFrame(a, b)
    if type(a) ~= "table" or type(b) ~= "table" or #a ~= 12 or #b ~= 12 then return false end
    for i = 1, 12 do
        if not finite(a[i]) or not finite(b[i]) or math.abs(a[i] - b[i]) > FRAME_TOLERANCE then return false end
    end
    return true
end

local function compareSignature(a, b)
    if type(a) ~= "table" or #a ~= 6 or type(a[1]) ~= "table" or type(a[2]) ~= "table"
        or type(a[6]) ~= "table" or #a[6] ~= 2 then return nil, "invalid signature" end
    if #a[1] ~= #b[1] then return nil, "mesh count" end
    for i, part in ipairs(a[1]) do
        local live = b[1][i]
        if not same(part[1], live[1]) or part[2] ~= live[2] then return nil, "mesh identity" end
        if not same(part[4], live[4]) then return nil, "mesh scale" end
        if not same(part[5], live[5]) then return nil, "mesh bone mapping" end
        if not nearFrame(part[3], live[3]) then return nil, "mesh frame " .. i end
    end
    if #a[2] ~= #b[2] then return nil, "bone count" end
    for i, bone in ipairs(a[2]) do
        local live = b[2][i]
        if bone[1] ~= live[1] then return nil, "bone path" end
        if not nearFrame(bone[2], live[2]) then
            return nil, "bone pose " .. tostring(bone[1])
        end
    end
    for i = 3, 5 do if not same(a[i], b[i]) then return nil, "head/bone mapping " .. i end end
    if not nearFrame(a[6][2], b[6][2]) then return nil, "root up" end
    -- Root center cancels out of the head-plane comparison. It only affects
    -- the broad sphere. Keep local boxes unchanged and conservatively enlarge
    -- that sphere by the center displacement (triangle inequality).
    local old, new = a[6][1], b[6][1]
    if type(old) ~= "table" or #old ~= 12 or type(new) ~= "table" or #new ~= 12 then return nil, "root center" end
    local squared = 0
    for i = 1, 3 do
        if not finite(old[i]) or not finite(new[i]) then return nil, "root center" end
        squared = squared + (old[i] - new[i])^2
    end
    return math.sqrt(squared) / 10000
end

local function insertRow(buckets, key, sig, row, serialized, component)
    local bucket = buckets[key] or {}
    buckets[key] = bucket
    if bucket[serialized] ~= nil then
        bucket[serialized].ambiguous = true -- ambiguous authoring data must not win
    else
        bucket[serialized] = {signature = sig, definition = row, component = component}
    end
end

if registryOk and type(Registry) == "table" and Registry.schemaVersion == VERSION and type(Registry.entries) == "table" then
    for _, row in ipairs(Registry.entries) do
        if type(row) == "table" and type(row.key) == "string" and type(row.signature) == "string" then
            local ok, parsed = pcall(function() return HttpService:JSONDecode(row.signature) end)
            if ok and type(parsed) == "table" then
                insertRow(byKey, row.key, parsed, row.definition, row.signature, row.component)
            else
                warn("[game1][hitbox-assets] malformed signature; ignored")
            end
        else
            warn("[game1][hitbox-assets] malformed registry entry; ignored")
        end
    end
else
    warn("[game1][hitbox-assets] incompatible registry schema; migration oracle retained")
end

local function lookup(bucket, binding, sig)
    if not bucket or not sig then return nil, "uncaptured or ambiguous assembly" end
    local serialized = HttpService:JSONEncode(sig)
    local exact = bucket[serialized]
    if exact and exact.ambiguous then return nil, "duplicate signature" end
    if exact then return decode(exact.definition, binding), "invalid bounds" end
    local matched, delta, reason = nil, nil, "signature mismatch"
    for _, row in pairs(bucket) do
        if row then
            local distance, why = compareSignature(row.signature, sig)
            if distance then
                if row.ambiguous then return nil, "duplicate nearby signature" end
                if matched then return nil, "ambiguous nearby signatures" end
                matched, delta = row, distance
            else
                reason = why
            end
        end
    end
    if not matched then return nil, reason end
    local definition = decode(matched.definition, binding)
    if not definition then return nil, "invalid bounds" end
    -- Include quantization slack in the broad phase only; narrow boxes remain
    -- byte-for-byte the captured bounds. No change to hit or headshot tests.
    definition.broadRadius = definition.broadRadius + delta + 0.005
    return definition
end

function Definitions.Signature(binding)
    local ok, result = pcall(signature, binding)
    if ok then return result end
    warn("[game1][hitbox-assets] signature failed: " .. tostring(result))
    return nil
end

function Definitions.SessionLookup(binding, key, sig)
    return lookup(sessionByKey[key], binding, sig)
end

function Definitions.Lookup(binding, key, sig)
    sig = sig or Definitions.Signature(binding)
    local ok, definition, reason = pcall(lookup, byKey[key], binding, sig)
    if not ok then reason, definition = tostring(definition), nil end
    if definition and not accepted[key] then
        accepted[key] = true
        print("[game1][hitbox-assets] asset definition accepted: " .. key)
    end
    if not definition and next(byKey) and not warned[key] then
        warned[key] = true
        warn("[game1][hitbox-assets] " .. tostring(reason) .. "; using migration oracle: " .. key)
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
    return result and HttpService:JSONEncode(result)
end

local function encodeBox(box)
    return {kind = box.kind, recordIndex = box.recordIndex, boneName = box.boneName,
        center = vector(box.localCFrame.Position), size = vector(box.size)}
end

local function encodeDefinition(definition)
    local body = {}
    for _, box in ipairs(definition.bodyBoxes) do table.insert(body, encodeBox(box)) end
    return {broadRadius = definition.broadRadius, sourceVertexCount = definition.sourceVertexCount,
        bodyBoxes = body, headBox = definition.headBox and encodeBox(definition.headBox) or nil}
end

function Definitions.Remember(key, sig, definition)
    if not sig or sessionCount >= SESSION_LIMIT then return end
    local serialized = HttpService:JSONEncode(sig)
    local bucket = sessionByKey[key]
    if bucket and bucket[serialized] ~= nil then return end
    insertRow(sessionByKey, key, sig, encodeDefinition(definition), serialized)
    sessionCount += 1
end

function Definitions.AuthoringRow(binding, key, definition, componentNames, rawHead)
    assert(RunService:IsStudio(), "hitbox authoring is Studio-only")
    local sig = HttpService:JSONEncode(assert(signature(binding, componentNames), "unpublished or ambiguous mesh/bone identity"))
    local encoded = encodeDefinition(definition)
    -- Test the actual serialized representation through the production decoder.
    local decoded = assert(decode(HttpService:JSONDecode(HttpService:JSONEncode(encoded)), binding), "hitbox roundtrip failed")
    local function compare(a, b)
        assert(a.kind == b.kind and a.recordIndex == b.recordIndex and a.boneName == b.boneName
            and (a.size - b.size).Magnitude <= 0.00001
            and (a.localCFrame.Position - b.localCFrame.Position).Magnitude <= 0.00001,
            "hitbox roundtrip mismatch")
    end
    assert(math.abs(decoded.broadRadius - definition.broadRadius) <= 0.00001 and decoded.sourceVertexCount == definition.sourceVertexCount
        and #decoded.bodyBoxes == #definition.bodyBoxes and (decoded.headBox ~= nil) == (definition.headBox ~= nil),
        "hitbox roundtrip metadata mismatch")
    for i, box in ipairs(definition.bodyBoxes) do compare(box, decoded.bodyBoxes[i]) end
    if definition.headBox then compare(definition.headBox, decoded.headBox) end
    local row = {key = key, signature = sig, definition = encoded}
    if componentNames then
        row.component = {dependencies = componentNames}
        if rawHead then
            row.component.rawHead = {minimum = vector(rawHead.minimum), maximum = vector(rawHead.maximum)}
        end
    end
    return row
end

-- Character components share the same versioned registry, decoder and
-- compatibility rules. No whole-appearance combinatorial key is persisted.
function Definitions.ComponentBinding(binding, index)
    local single = table.clone(binding)
    single.records = {binding.records[index]}
    return single
end

function Definitions.ComponentDependencies(record)
    local names, seen = {}, {}
    for _, vertex in pairs(record.geometry.vertices) do
        for _, influence in ipairs(vertex.influences) do
            if not seen[influence.boneName] then
                seen[influence.boneName] = true
                table.insert(names, influence.boneName)
            end
        end
    end
    table.sort(names)
    return names
end

local function lookupComponent(binding, bucket)
    if not bucket then return nil, "uncaptured component" end
    local exact, nearby, reason = nil, {}, nil
    for _, row in pairs(bucket) do
        local component = row.component
        if type(component) == "table" and type(component.dependencies) == "table" then
            local sig = signature(binding, component.dependencies)
            local delta, why
            if sig then delta, why = compareSignature(row.signature, sig) end
            if delta then
                local candidate = {row = row, delta = delta}
                if same(row.signature, sig) then
                    if exact then return nil, "ambiguous exact component signature" end
                    exact = candidate
                else
                    table.insert(nearby, candidate)
                end
            else reason = why or "missing component bone" end
        end
    end
    if not exact and #nearby > 1 then return nil, "ambiguous nearby component signatures" end
    local candidate = exact or nearby[1]
    if not candidate then return nil, reason or "invalid component metadata" end
    local row = candidate.row
    if row.ambiguous then return nil, "duplicate component signature" end
    local decoded = decode(row.definition, binding)
    if not decoded then return nil, "invalid component bounds" end
    local component = row.component
    if component.rawHead then
        local minimum = readVector(component.rawHead.minimum, false)
        local maximum = readVector(component.rawHead.maximum, false)
        if not minimum or not maximum or not decoded.headBox or minimum.X > maximum.X
            or minimum.Y > maximum.Y or minimum.Z > maximum.Z then return nil, "invalid raw head bounds" end
        decoded.rawHead = {minimum = minimum, maximum = maximum}
    elseif decoded.headBox then return nil, "missing raw head bounds" end
    decoded.broadRadius = decoded.broadRadius + candidate.delta + 0.005
    return decoded
end

function Definitions.LookupComponent(binding, key)
    local ok, definition, reason = pcall(lookupComponent, binding, byKey[key])
    if not ok then return nil, tostring(definition) end
    return definition, reason
end

function Definitions.Record(key, sig, definition)
    if not captureEnabled or capturedCount >= CAPTURE_LIMIT then return end
    local id = HttpService:JSONEncode({key, sig})
    if captures[id] then return end
    captures[id] = {key = key, signature = sig, definition = encodeDefinition(definition)}
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
