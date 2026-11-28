--!strict
-- Optional warm RPC. Never builds a character or consumes a preview cache slot.
-- The server owns the allowlist and the lightweight typed geometry sources.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("character")
local Plan = require(script.Parent:WaitForChild("CharacterCreationWarmPlan"))
local Registry = require(Shared:WaitForChild("CharacterRegistry"))
local Catalog = require(Shared:WaitForChild("CharacterCreationAppearanceRegistry"))
local Service = {}
local MAX_SOURCES = 96
local MAX_PARTS = 16

function Service.Bind(remotes: Folder, loadAsset: (number) -> Model?)
    local plan = Plan.Build(Registry, Catalog)
    local folder = Instance.new("Folder")
    folder.Name = "Game1CharacterWarmSources"
    folder.Parent = ReplicatedStorage
    local byMesh: {[string]: string} = {}
    local results: {[number]: any} = {}
    local retryAt: {[number]: number} = {}
    local count = 0
    local busy = false
    local remote = Instance.new("RemoteFunction")
    remote.Name = "CharacterCreationWarmComponent"
    remote.OnServerInvoke = function(player: Player, index: any)
        if player:GetAttribute("CharacterCreationPending") ~= true or player:GetAttribute("CharacterCreationStatus") ~= "creation" then
            return {ok = false, error = "creation_not_pending"}
        end
        if type(index) ~= "number" or index % 1 ~= 0 or index < 1 or index > #plan + 1 then
            return {ok = false, error = "invalid_component_index"}
        end
        if index == #plan + 1 then return {ok = true, done = true} end
        if results[index] then return results[index] end
        if busy then return {ok = false, error = "warm_busy"} end
        if (retryAt[index] or 0) > os.clock() then return {ok = false, error = "warm_retry_cooldown"} end
        busy = true
        local staged: {MeshPart} = {}
        local ok, result = pcall(function()
            local record = plan[index]
            local model = loadAsset(record.assetId)
            if not model then return {ok = false, error = "component_unavailable"} end
            if player:GetAttribute("CharacterCreationStatus") ~= "creation" then
                return {ok = false, error = "creation_not_pending"}
            end
            local meshNames, images, seen, stagedNames = {}, {}, {}, {}
            local parts = 0
            for id in pairs(record.atlases) do images["rbxassetid://" .. id] = true end
            for _, part in ipairs(model:GetDescendants()) do
                if part:IsA("MeshPart") then
                    parts += 1
                    if parts > MAX_PARTS then return {ok = false, error = "component_part_limit"} end
                    if part.TextureID ~= "" then images[part.TextureID] = true end
                    local meshId = part.MeshId
                    if meshId ~= "" and not seen[meshId] then
                        seen[meshId] = true
                        local name = byMesh[meshId]
                        if not name then
                            if count + #staged >= MAX_SOURCES then return {ok = false, error = "warm_source_limit"} end
                            local copy = part:Clone()
                            assert(copy, "warm source not archivable")
                            table.insert(staged, copy)
                            copy:ClearAllChildren()
                            copy.TextureID = ""
                            copy.Anchored = true
                            copy.CanCollide = false; copy.CanTouch = false; copy.CanQuery = false
                            name = "Mesh" .. tostring(count + #staged)
                            copy.Name = name
                            stagedNames[meshId] = name
                        end
                        table.insert(meshNames, name)
                    end
                elseif part:IsA("Decal") or part:IsA("Texture") then
                    if part.Texture ~= "" then images[part.Texture] = true end
                end
            end
            if parts == 0 then return {ok = false, error = "component_has_no_mesh"} end
            local textures = {}
            for uri in pairs(images) do table.insert(textures, uri) end
            table.sort(textures)
            -- Publish only after the whole component fits the budget.
            for _, source in ipairs(staged) do source.Parent = folder end
            for meshId, name in pairs(stagedNames) do byMesh[meshId] = name end
            count += #staged
            table.clear(staged)
            return {ok = true, meshes = meshNames, images = textures, count = #plan}
        end)
        for _, source in ipairs(staged) do source:Destroy() end
        busy = false
        if not ok then
            retryAt[index] = os.clock() + 15
            warn("[game1][character-creation] component warm: " .. tostring(result))
            return {ok = false, error = "warm_failed"}
        end
        if result.ok then results[index] = result
        elseif result.error ~= "creation_not_pending" then retryAt[index] = os.clock() + 15 end
        return result
    end
    remote.Parent = remotes
end

return table.freeze(Service)
