-- Authoring-only capture of a disposable clone of the synchronized FULL asset.
-- No live spawn, no Workspace publication, no AI, no collision-group writes.
local Preview = require(script.Parent.StudioTimelinePreview)
local IdlePose = require(script.Parent.StudioMnpcIdlePose)
local Capture = {}

local function child(parent, name)
    return assert(parent:FindFirstChild(name), "MNPC missing " .. name .. "; sync Rojo and templates")
end

local function module(parent, name)
    local node = child(parent, name)
    assert(node:IsA("ModuleScript"), "MNPC expected ModuleScript: " .. name)
    return require(node)
end

local function templateAt(path, modelId)
    local segments = string.split(path, ".")
    assert(segments[1] == "ServerStorage", "MNPC invalid template path")
    local node = game:GetService("ServerStorage")
    for i = 2, #segments do node = child(node, segments[i]) end
    assert(node:IsA("Model") and tostring(node:GetAttribute("Game1ModelAssetId") or "") == modelId,
        "MNPC template publication differs; Sync Model + Atlas first: " .. path)
    return node
end

local function id(value)
    if value == "" then return "" end
    return assert(tostring(value):match("^rbxassetid://(%d+)$"), "MNPC unsupported asset content: " .. tostring(value))
end

local function vector(v) return {v.X, v.Y, v.Z} end
local function frame(cf) return {cf:GetComponents()} end
local function pathOf(root, node)
    local names = {}
    while node ~= root do
        assert(node and node.Parent and #names < 32, "MNPC invalid captured path")
        assert(#node.Name > 0 and #node.Name <= 128 and not string.find(node.Name, "/", 1, true), "MNPC unsupported instance name")
        -- An absolute hierarchy identifier must not collapse two siblings.
        local count = 0
        for _, sibling in node.Parent:GetChildren() do
            if sibling.Name == node.Name then count += 1 end
        end
        assert(count == 1, "MNPC duplicate captured sibling: " .. node.Name)
        table.insert(names, 1, node.Name)
        node = node.Parent
    end
    return table.concat(names, "/")
end

local function captureFrames(assembly, visual, equipment, rootFrame)
    local meshes, bones = {}, {}
    local function scan(model, owner)
        for _, node in model:GetDescendants() do
            if node:IsA("Bone") then
                assert(#bones < 512, "MNPC bone capture budget exceeded")
                table.insert(bones, {path = pathOf(assembly, node), owner = owner, name = node.Name,
                    rest = frame(rootFrame:ToObjectSpace(node.WorldCFrame)),
                    posed = frame(rootFrame:ToObjectSpace(node.TransformedWorldCFrame)),
                    localTransform = frame(node.Transform)})
            elseif node:IsA("BasePart") and node.Transparency < 0.99 then
                local lower = string.lower(node.Name)
                if lower == "rootpart" or lower == "humanoidrootpart" or lower == "rootcollider" or lower == "rig_carrier" then continue end
                assert(node:IsA("MeshPart"), "MNPC visible non-mesh part unsupported: " .. node.Name)
                assert(#meshes < 64, "MNPC mesh capture budget exceeded")
                local appearance = node:FindFirstChildOfClass("SurfaceAppearance")
                local colorMap = if appearance then id(appearance.ColorMap) else ""
                -- Additional PBR maps are recorded as an explicit unsupported
                -- bake boundary, not silently treated as an albedo texture.
                table.insert(meshes, {path = pathOf(assembly, node), owner = owner, meshId = id(node.MeshId),
                    textureId = id(node.TextureID), colorMap = colorMap,
                    normalMap = if appearance then id(appearance.NormalMap) else "",
                    roughnessMap = if appearance then id(appearance.RoughnessMap) else "",
                    metalnessMap = if appearance then id(appearance.MetalnessMap) else "",
                    frame = frame(rootFrame:ToObjectSpace(node.CFrame)), size = vector(node.Size), meshSize = vector(node.MeshSize),
                    color = {node.Color.R, node.Color.G, node.Color.B}, material = node.Material.Name,
                    transparency = node.Transparency})
            end
        end
    end
    scan(visual, "body")
    assert(#meshes > 0, "MNPC no visible body MeshParts")
    for _, hand in {"right", "left"} do
        if equipment[hand] then
            local before = #meshes
            scan(equipment[hand], hand)
            assert(#meshes > before, "MNPC equipped weapon has no visible mesh: " .. hand)
        end
    end
    assert(#bones > 0, "MNPC no captured skeleton")
    table.sort(meshes, function(a,b) return a.path < b.path end)
    table.sort(bones, function(a,b) return a.path < b.path end)
    return meshes, bones
end

function Capture.Run(data)
    local shared = child(game:GetService("ReplicatedStorage"), "Game1Shared")
    local server = child(game:GetService("ServerScriptService"), "Game1Server")
    local isNpc = data.kind == "npc"
    assert(isNpc or data.kind == "monster", "MNPC invalid kind")
    local domain = child(shared, data.kind)
    local serverDomain = child(server, data.kind)
    local prefix = if isNpc then "Npc" else "Monster"
    local registry = module(domain, prefix .. "Registry")
    local definition = (if isNpc then registry.npcs else registry.monsters)[data.slug]
    assert(definition and definition.status == "PUBLISHED" and tostring(definition.modelAssetId) == data.modelId,
        "MNPC FULL registry differs; sync Rojo")
    local template = templateAt(definition.serverStoragePath, data.modelId)
    local profile = module(domain, prefix .. "AnimationRegistry").profiles[data.slug]
    assert(profile and profile.skeletonSignature == definition.skeletonSignature, "MNPC animation skeleton signature differs")
    local assembly, sequence = nil, nil
    local ok, result = xpcall(function()
        assembly = assert(template:Clone(), "MNPC cannot clone template")
        for _, node in assembly:GetDescendants() do
            if node:IsA("LuaSourceContainer") or node:IsA("Animator") then node:Destroy()
            elseif node:IsA("BasePart") then node.Anchored = true end
        end
        local visual = assembly:FindFirstChild("ImportedRig")
        assert(visual and visual:IsA("Model"), "MNPC canonical ImportedRig required")
        local actor = child(server, "actor")
        local rootFrame = module(actor, "MnpcNavigationShell").RootFrame(Vector3.zero, 0)
        local plan = assert(module(actor, "MnpcRigGeometry").Plan(assembly, rootFrame, Vector3.zero, 0,
            if isNpc then "NPC" else "Monster"), "MNPC cannot determine runtime root alignment")
        assembly:PivotTo(rootFrame * plan.pivotOffset)
        local weapons, weaponSet = {}, ""
        local rows = profile.slots.idle or {}
        if isNpc then
            local context = module(serverDomain, "NpcEquipmentService").Resolve(data.slug)
            local equipService = module(child(server, "weapon"), "WeaponEquipService")
            local expected = data.equipment
            local found = {}
            for _, item in context.items do
                local wanted = expected[item.hand]
                assert(wanted and wanted.slug == item.slug, "MNPC equipment registry differs")
                local row, weaponTemplate = equipService.ResolveVisual(item.slug)
                assert(row and weaponTemplate and tostring(row.modelAssetId) == wanted.modelId, "MNPC weapon registry differs")
                assert(tostring(weaponTemplate:GetAttribute("Game1ModelAssetId") or "") == wanted.modelId,
                    "MNPC weapon template differs; Sync Model + Atlas first")
                local weapon, _, err = equipService.EquipVisual(assembly, item.slug, item.hand,
                    if item.hand == "right" then "EquippedWeaponRight" else "EquippedWeaponLeft")
                assert(weapon, "MNPC weapon mount failed: " .. tostring(err))
                weapons[item.hand] = weapon
                found[item.hand] = true
            end
            for hand in pairs(expected) do assert(found[hand], "MNPC expected weapon missing: " .. hand) end
            weaponSet = context.weaponSet
            assert(module(serverDomain, "NpcAnimationRigBinding").Align(visual, data.slug, profile, weaponSet), "MNPC clip root alignment failed")
            rows = module(serverDomain, "NpcAnimationTracks").PublishedRows(profile, "idle", weaponSet)
        else
            module(serverDomain, "MonsterRigBuilder").EnsureRuntimeAnimationRoot(visual)
        end
        local idle = nil
        for _, row in rows do
            if row.role == "base" and row.sourceSlot == "idle" then idle = row; break end
        end
        assert(idle and idle.looped == true, "MNPC published base idle required")
        local pinned = false
        for _, candidate in data.idles do
            if candidate.clipId == idle.clipId and candidate.assetId == tostring(idle.assetId) then pinned = true; break end
        end
        assert(pinned, "MNPC idle registry differs from current published Host clip")
        sequence = Preview.LoadSequence(game:GetService("AnimationClipProvider"), assert(tonumber(idle.assetId)))
        local pose = IdlePose.Apply(visual, sequence, data.phase)
        -- Same rigid-joint equation as the Timeline Editor; no physics step.
        Preview.RefreshAccessories(assembly)
        local meshes, bones = captureFrames(assembly, visual, weapons, rootFrame)
        return {animationId = tostring(idle.assetId), clipId = idle.clipId, weaponSet = weaponSet,
            pose = pose, meshes = meshes, bones = bones}
    end, debug.traceback)
    if sequence then sequence:Destroy() end
    if assembly then assembly:Destroy() end
    assert(ok, tostring(result))
    return result
end
return table.freeze(Capture)
