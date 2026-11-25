--!strict
-- Server creates shared canonical preview templates; each client clones them locally.
-- No physics, combat service or player Character is created for a preview.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Builder = require(script.Parent:WaitForChild("CharacterAssemblyBuilder"))
local Appearance = require(script.Parent:WaitForChild("CharacterCreationAppearanceService"))
local Service = {}
Service.__index = Service

function Service.new(loadAsset: (number) -> Model?)
    local folder = ReplicatedStorage:FindFirstChild("Game1CharacterCreationTemplates") or Instance.new("Folder")
    folder.Name = "Game1CharacterCreationTemplates"
    folder.Parent = ReplicatedStorage
    return setmetatable({loadAsset = loadAsset, folder = folder, cache = {} :: {[string]: string}, count = 0,
        building = {} :: {[string]: boolean}}, Service)
end

function Service:Prepare(archetype: string, selection: any): (string?, string?)
    local recipe, checked, problem = Appearance.Resolve(archetype, selection)
    if not recipe then return nil, problem end
    local key = Appearance.VisualKey(archetype, checked)
    local cached = self.cache[key]
    if cached and self.folder:FindFirstChild(cached) then return cached, nil end
    -- Concurrent players may request the same template. Never publish duplicates.
    local checks = 0
    while self.building[key] and checks < 200 do
        checks += 1
        task.wait(0.05)
    end
    if self.building[key] then return nil, "preview_build_timeout" end
    cached = self.cache[key]
    if cached and self.folder:FindFirstChild(cached) then return cached, nil end
    -- Bound once per server, not per player. New assets after publication need a new server.
    if self.count >= 32 then return nil, "preview_variant_limit" end
    self.building[key] = true
    -- Geometry cache is independent of the requesting player's colors.
    local neutralRecipe, _, neutralProblem = Appearance.Resolve(archetype, {
        hair = checked.hair, head = checked.head, eyes = checked.eyes, eyebrows = checked.eyebrows,
    })
    if not neutralRecipe then
        self.building[key] = nil
        return nil, neutralProblem
    end
    local ok, model = pcall(Builder.Build, neutralRecipe, self.loadAsset)
    if not ok or not model then
        self.building[key] = nil
        return nil, "preview_build_failed: " .. tostring(model)
    end
    local template = model :: Model
    for _, descendant in ipairs(template:GetDescendants()) do
        if descendant:IsA("BasePart") then
            descendant.Anchored = true
            descendant.CanCollide = false
            descendant.CanTouch = false
            descendant.CanQuery = false
        end
    end
    self.count += 1
    local id = "Preview" .. tostring(self.count)
    template.Name = id
    template.Archivable = true
    template.Parent = self.folder
    self.cache[key] = id
    self.building[key] = nil
    return id, nil
end

function Service:Bind(remotes: Folder)
    local remote = remotes:FindFirstChild("CharacterCreationPreview") or Instance.new("RemoteFunction")
    assert(remote:IsA("RemoteFunction"), "CharacterCreationPreview must be a RemoteFunction")
    remote.Name = "CharacterCreationPreview"
    remote.Parent = remotes
    local busy: {[Player]: boolean} = {}
    remote.OnServerInvoke = function(player: Player, archetype: any, choice: any)
        if player:GetAttribute("CharacterCreationPending") ~= true then
            return {ok = false, error = "selection_not_pending"}
        end
        if busy[player] then return {ok = false, error = "preview_busy"} end
        busy[player] = true
        local ok, id, reason = pcall(self.Prepare, self, archetype, choice)
        busy[player] = nil
        if not ok then
            warn("[game1][character-creation] preview exception: " .. tostring(id))
            return {ok = false, error = "preview_unavailable"}
        end
        if not id then return {ok = false, error = reason} end
        return {ok = true, template = id}
    end
end
return Service
