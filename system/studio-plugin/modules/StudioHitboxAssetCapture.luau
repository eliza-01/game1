-- Offline capture of the exact Runtime MNPC assembly and the production
-- hitbox oracle. The detached entity never joins Workspace or AI/physics.
local Capture = {}
local CharacterCapture = require(script.Parent.StudioCharacterHitboxCapture)

local function child(parent, name)
    return assert(parent:FindFirstChild(name), "Hitbox capture missing " .. name .. "; sync Rojo")
end

local function module(parent, name)
    return require(child(parent, name))
end

local function templateAt(path, modelId)
    local segments = string.split(path, ".")
    assert(segments[1] == "ServerStorage", "invalid published template path")
    local node = game:GetService("ServerStorage")
    for i = 2, #segments do node = child(node, segments[i]) end
    assert(node:IsA("Model") and tostring(node:GetAttribute("Game1ModelAssetId") or "") == modelId,
        "template publication differs; Sync Model + Atlas first")
    return node
end

function Capture.Run(data)
    if data.kind == "character" then return CharacterCapture.Run(data) end
    local isNpc = data.kind == "npc"
    assert(isNpc or data.kind == "monster", "invalid hitbox actor kind")
    local shared = child(game:GetService("ReplicatedStorage"), "Game1Shared")
    local server = child(game:GetService("ServerScriptService"), "Game1Server")
    local domain = child(shared, data.kind)
    local serverDomain = child(server, data.kind)
    local prefix = if isNpc then "Npc" else "Monster"
    local registry = module(domain, prefix .. "Registry")
    local definition = (if isNpc then registry.npcs else registry.monsters)[data.slug]
    assert(definition and definition.status == "PUBLISHED" and tostring(definition.modelAssetId) == data.modelId,
        "FULL registry differs; sync Rojo")
    local template = templateAt(definition.serverStoragePath, data.modelId)
    local actor = child(server, "actor")
    local lifecycle = module(actor, "MnpcEntityLifecycle")
    -- Edit-mode templates can change in place. Do not keep a stale plan.
    module(actor, "MnpcRigGeometry").Invalidate(template)
    local entity = nil
    local ok, result = xpcall(function()
        local root
        local kind = if isNpc then "NPC" else "Monster"
        entity, root = lifecycle.Create("HitboxAuthoring", Vector3.zero, 0, kind, true)
        entity:SetAttribute(if isNpc then "NpcSlug" else "MonsterSlug", data.slug)
        local prepared = lifecycle.PrepareShell(entity, root, template, Vector3.zero, 0, kind)
        local visual, lease = lifecycle.AttachRig(entity, root, template, Vector3.zero, 0, kind, prepared)
        assert(visual and lease, "cannot assemble FULL rig")
        if isNpc then
            local equipment = module(serverDomain, "NpcEquipmentService")
            local context = equipment.Resolve(data.slug)
            local equipService = module(child(server, "weapon"), "WeaponEquipService")
            local found = {}
            for _, item in ipairs(context.items) do
                local expected = data.equipment[item.hand]
                assert(expected and expected.slug == item.slug, "NPC loadout differs; sync Rojo")
                local row, weaponTemplate = equipService.ResolveVisual(item.slug)
                assert(row and weaponTemplate and tostring(row.modelAssetId) == expected.modelId
                    and tostring(weaponTemplate:GetAttribute("Game1ModelAssetId") or "") == expected.modelId,
                    "NPC weapon publication differs; Sync Model + Atlas first")
                found[item.hand] = true
            end
            for hand in pairs(data.equipment) do assert(found[hand], "missing expected NPC equipment") end
            local weaponSet = equipment.Equip(entity, data.slug, context, lease)
            for _, item in ipairs(context.items) do
                local name = if item.hand == "right" then "EquippedWeaponRight" else "EquippedWeaponLeft"
                assert(entity:FindFirstChild(name), "NPC equipment mount failed: " .. item.slug)
            end
            local profile = module(domain, "NpcAnimationRegistry").profiles[data.slug]
            assert(module(serverDomain, "NpcAnimationRigBinding").Align(visual, data.slug, profile, weaponSet),
                "NPC animation root alignment failed")
        else
            module(serverDomain, "MonsterRigBuilder").EnsureRuntimeAnimationRoot(visual)
        end
        local hitboxes = module(child(server, "combat"), "EntityHitboxService")
        local row = hitboxes.CaptureAsset(entity, visual)
        return {schemaVersion = 2, entries = {row}}
    end, debug.traceback)
    if entity then entity:Destroy() end
    if not ok then error(result) end
    return result
end

return table.freeze(Capture)
