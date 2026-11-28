-- Studio Edit only. Reuse the real assembled character and visual placement;
-- no player, animation, equipment, Workspace parent or combat registration.
local Capture = {}
local function child(parent,name)
    return assert(parent:FindFirstChild(name), "Missing " .. name .. "; sync Rojo")
end
local function module(parent,name) return require(child(parent,name)) end
local function matches(part, expected)
    return part and tostring(part.asset_id) == expected.asset_id and part.id == expected.id
        and part.revision == expected.revision
end
function Capture.Run(data)
    local runService = game:GetService("RunService")
    assert(runService:IsStudio() and not runService:IsRunning(), "Studio Edit required")
    local shared = child(child(game:GetService("ReplicatedStorage"), "Game1Shared"), "character")
    local server = child(game:GetService("ServerScriptService"), "Game1Server")
    local domain = child(server, "character")
    local builder = module(domain, "CharacterAssemblyBuilder")
    local appearance = module(domain, "CharacterCreationAppearanceService")
    local rigService = module(domain, "CharacterRigService")
    local loader = module(domain, "CharacterAssetTemplate")
    local hitboxes = module(child(server, "combat"), "EntityHitboxService")
    local row
    for _, item in ipairs(module(shared, "CharacterRegistry").archetypes) do
        if item.id == data.slug then row = item break end
    end
    assert(row and row.status == "ASSEMBLY_READY" and row.assembly.ready and tostring(row.assembly.rig.asset_id) == data.modelId
        and row.assembly.fingerprint == data.assemblyFingerprint,
        "Character registry changed; sync Rojo")
    assert(type(data.variants) == "table" and #data.variants > 0 and #data.variants <= 32, "invalid capture plan")
    local assets, entity, template = {}, nil, nil
    local ok, result = xpcall(function()
        local entries = {}
        local function load(assetId)
            if not assets[assetId] then assets[assetId] = assert(loader.Load(assetId), "Cannot load publication " .. assetId) end
            return assets[assetId]
        end
        for _, variant in ipairs(data.variants) do
            local recipe = row.assembly
            if not variant.base then
                local selected, problem
                recipe, selected, problem = appearance.Resolve(data.slug, variant.selection)
                assert(recipe, problem)
            end
            assert(matches(recipe.rig, variant.rig), "rig publication changed; sync Rojo")
            for slot, expected in pairs(variant.parts) do
                assert(matches(recipe.parts[slot], expected), "component publication changed: " .. slot)
            end
            for slot in pairs(recipe.parts) do assert(variant.parts[slot], "unexpected component " .. slot) end
            template = builder.Build(recipe, load)
            entity = Instance.new("Model")
            entity.Name = "CharacterHitboxAuthoring"
            entity:SetAttribute("CharacterArchetype", data.slug)
            local visual = assert(rigService.BuildHitboxAuthoring(entity, template), "cannot place character rig")
            for _, captured in ipairs(hitboxes.CaptureCharacterComponents(entity, visual)) do
                table.insert(entries, captured)
            end
            entity:Destroy(); entity = nil
            template:Destroy(); template = nil
        end
        return {schemaVersion = 2, entries = entries, variants = #data.variants}
    end, debug.traceback)
    if entity then entity:Destroy() end
    if template then template:Destroy() end
    for _, asset in pairs(assets) do asset:Destroy() end
    if not ok then error(result) end
    return result
end
return table.freeze(Capture)
