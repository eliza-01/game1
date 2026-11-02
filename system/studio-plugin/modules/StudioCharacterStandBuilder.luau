-- Studio authoring adapter for the SAME published assembly recipe and Builder
-- used by CharacterService. No second bind/atlas/mesh pipeline is implemented here.
local Builder = {}

local function registryRoot()
    local shared = game:GetService("ReplicatedStorage"):FindFirstChild("Game1Shared")
    assert(shared, "Game1Shared is absent. Run Rojo sync before assembling a character stand.")
    local character = shared:FindFirstChild("character")
    assert(character, "Game1Shared.character is absent")
    return character
end

function Builder.Profiles(): {any}
    local character = registryRoot()
    local registry = require(character:WaitForChild("CharacterRegistry"))
    local result = {}
    for _, row in ipairs(registry.archetypes or {}) do
        if row.visualMode == "assembly" and row.assembly and row.assembly.ready == true then
            table.insert(result, {id = row.id, label = tostring(row.displayName or row.id), mode = "assembly", row = row})
        elseif row.visualMode == "model" and row.model and tonumber(row.model.assetId) then
            table.insert(result, {id = row.id, label = tostring(row.displayName or row.id), mode = "model", row = row})
        end
    end
    table.sort(result, function(a, b) return a.id < b.id end)
    return result
end

local function getBuilder()
    local server = nil
    for _, candidate in game:GetService("ServerScriptService"):GetChildren() do
        if candidate.Name == "Game1Server" and candidate:IsA("Script") then
            assert(server == nil, "multiple active Game1Server scripts")
            server = candidate
        end
    end
    assert(server, "active Game1Server Script is absent. Run Rojo sync before assembling a character stand.")
    local character = server:FindFirstChild("character")
    assert(character, "Game1Server.character is absent")
    local module = character:FindFirstChild("CharacterAssemblyBuilder")
    assert(module and module:IsA("ModuleScript"), "CharacterAssemblyBuilder is absent")
    return require(module)
end

local function loadPublished(assetService: any, id: number): Model
    assert(id > 0 and id == math.floor(id), "invalid published Model Asset ID")
    local loaded = assetService:LoadAssetAsync(id)
    assert(loaded and loaded:IsA("Model"), "published asset is not a Model: " .. id)
    return loaded
end

local function prepareLegacy(assetService: any, row: any): Model
    local assetId = assert(tonumber(row.model.assetId), "legacy character lacks Model Asset ID")
    local loaded = loadPublished(assetService, assetId)
    local imported: Instance = loaded
    if #loaded:GetChildren() == 1 then
        imported = loaded:GetChildren()[1]
        imported.Parent = nil
        loaded:Destroy()
    end
    local rig: Model
    if imported:IsA("Model") then
        rig = imported
    else
        rig = Instance.new("Model")
        rig.Name = "ImportedRig"
        imported.Parent = rig
    end
    local wrapper = Instance.new("Model")
    wrapper.Name = "assembled_character"
    rig.Name = "ImportedRig"
    rig.Parent = wrapper
    local template = require(script.Parent.CharacterTemplate)
    template.EnsureCanonicalRoot(wrapper, rig)
    local host = rig:FindFirstChildWhichIsA("AnimationController", true)
    if host then host.Parent = wrapper else
        host = Instance.new("AnimationController")
        host.Parent = wrapper
    end
    if not host:FindFirstChildOfClass("Animator") then
        Instance.new("Animator").Parent = host
    end
    return wrapper
end

function Builder.Build(assetService: any, profile: any): Model
    local row = profile.row
    local wrapper: Model
    if profile.mode == "assembly" then
        local cached = {}
        local loadedAssets = {}
        local ok, result = xpcall(function()
            local assemblyBuilder = getBuilder()
            return assemblyBuilder.Build(row.assembly, function(id: number): Model
                if not cached[id] then
                    local loaded = loadPublished(assetService, id)
                    cached[id] = loaded
                    table.insert(loadedAssets, loaded)
                end
                return cached[id]
            end)
        end, debug.traceback)
        for _, item in ipairs(loadedAssets) do item:Destroy() end
        if not ok then error(result, 2) end
        wrapper = result
    else
        wrapper = prepareLegacy(assetService, row)
    end
    wrapper:SetAttribute("Game1CharacterTestStand", true)
    wrapper:SetAttribute("Game1AnimationProfileId", tostring(profile.id))
    wrapper:SetAttribute("Game1CharacterArchetype", tostring(profile.id))
    wrapper:SetAttribute("Game1SkeletonSignature", tostring(row.skeleton and row.skeleton.signature or ""))
    wrapper:SetAttribute("Game1TestStandVersion", 1)
    return wrapper
end

return table.freeze(Builder)
