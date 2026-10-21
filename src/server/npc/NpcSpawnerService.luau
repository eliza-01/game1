-- NPC population/death/respawn owner. Combat decisions and navigation live in separate services.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerStorage = game:GetService("ServerStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local NpcShared = Shared:WaitForChild("npc")
local NpcRegistry = require(NpcShared:WaitForChild("NpcRegistry"))
local NpcAnimationRegistry = require(NpcShared:WaitForChild("NpcAnimationRegistry"))
local NpcSpawnRegistry = require(script.Parent:WaitForChild("NpcSpawnRegistry"))
local CombatRoot = script.Parent.Parent:WaitForChild("combat")
local EntityHitboxService = require(CombatRoot:WaitForChild("EntityHitboxService"))
local DeathLifecycleService = require(CombatRoot:WaitForChild("DeathLifecycleService"))
local NpcRigFactory = require(script.Parent:WaitForChild("NpcRigFactory"))
local NpcAnimationService = require(script.Parent:WaitForChild("NpcAnimationService"))
local NpcEquipmentService = require(script.Parent:WaitForChild("NpcEquipmentService"))
local NpcCombatAIService = require(script.Parent:WaitForChild("NpcCombatAIService"))

local NpcSpawnerService = {}
local started = false
local states: {[string]: any} = {}
local random = Random.new()

local function folder(): Folder
    local current = Workspace:FindFirstChild("NPCs")
    if current and not current:IsA("Folder") then
        error("Workspace.NPCs must be a Folder")
    end
    if not current then
        current = Instance.new("Folder")
        current.Name = "NPCs"
        current.Parent = Workspace
    end
    return current :: Folder
end

local function modelAtPath(path: string): Model?
    local parts = string.split(path, ".")
    if parts[1] ~= "ServerStorage" then
        return nil
    end
    local instance: Instance? = ServerStorage
    for index = 2, #parts do
        instance = if instance then instance:FindFirstChild(parts[index]) else nil
        if not instance then
            return nil
        end
    end
    return if instance and instance:IsA("Model") then instance else nil
end

local function finite(value: any, fallback: number): number
    local n = tonumber(value)
    return if n and n == n and n > -math.huge and n < math.huge then n else fallback
end

local function spawnPosition(record: any): Vector3
    -- NPCs occupy the exact authored point, including underground rooms.
    local point = record.position or {}
    return Vector3.new(finite(point.x, 0), finite(point.y, 0), finite(point.z, 0))
end

local function release(state: any, entity: Model, scheduleRespawn: boolean)
    local entry = state.instances[entity]
    if not entry then
        return
    end
    state.instances[entity] = nil
    DeathLifecycleService.Cancel(entity)
    NpcCombatAIService.Unbind(entity)
    if entry.presentation then
        entry.presentation.Destroy()
    end
    EntityHitboxService.Detach(entity)
    if entity.Parent then
        entity:Destroy()
    end
    if scheduleRespawn then
        task.delay(math.max(0, finite(state.record.respawnSeconds, 10)), function()
            if state.active then
                state.fill()
            end
        end)
    end
end

local function spawnOne(state: any): boolean
    local record = state.record
    local slug = tostring(record.monsterSlug or "") -- internal spawn serialization is shared with monsters
    local definition = (NpcRegistry.npcs or {})[slug]
    if not definition or definition.status ~= "PUBLISHED" then
        warn("[game1][npc] NPC is missing or unpublished: " .. slug)
        return false
    end
    local template = modelAtPath(tostring(definition.serverStoragePath or ""))
    if not template then
        warn("[game1][npc] NPC template is not synced to ServerStorage: " .. slug)
        return false
    end
    local entity = template:Clone()
    entity.Name = slug .. "_" .. tostring(random:NextInteger(100000, 999999))
    entity.Parent = folder()
    local visual, root = NpcRigFactory.Create(entity, spawnPosition(record), finite(record.yawDegrees, 0))
    if not visual or not root then
        entity:Destroy()
        warn("[game1][npc] published model has no usable visual rig: " .. slug)
        return false
    end
    local stats = definition.stats or {}
    local hp = math.max(1, finite(stats.MaxHP, 100))
    entity:SetAttribute("Game1NpcRuntime", true)
    entity:SetAttribute("NpcSlug", slug)
    NpcEquipmentService.Equip(entity, slug)
    entity:SetAttribute("SpawnId", tostring(record.spawnId or ""))
    entity:SetAttribute("Damageable", true)
    entity:SetAttribute("LifeState", "Alive")
    entity:SetAttribute("InCombat", false)
    entity:SetAttribute("CombatState", "Peace")
    entity:SetAttribute("CombatUntilServerTime", 0)
    entity:SetAttribute("HP", hp)
    entity:SetAttribute("MaxHP", hp)
    entity:SetAttribute("Damage", math.max(0, finite(stats.Damage, 10)))
    entity:SetAttribute("Defense", math.max(0, finite(stats.Defense, 0)))
    entity:SetAttribute("CritChance", math.clamp(finite(stats.CritChance, 0), 0, 100))
    entity:SetAttribute("AttackSpeed", math.max(1, finite(stats.AttackSpeed, 100)))
    entity:SetAttribute("RunSpeed", math.max(0, finite(stats.RunSpeed, 50)))
    local hitbox = EntityHitboxService.Attach(entity, visual)
    entity:SetAttribute("CombatHitboxCount", hitbox.count)
    local profile = (NpcAnimationRegistry.profiles or {})[slug]
    local presentation = NpcAnimationService.Create(entity, visual, profile)
    local entry = { root = root, visual = visual, presentation = presentation, dying = false }
    state.instances[entity] = entry
    NpcCombatAIService.Bind(entity, root, presentation)
    entity:GetAttributeChangedSignal("LifeState"):Connect(function()
        if state.instances[entity] ~= entry then
            return
        end
        if entity:GetAttribute("LifeState") == "Dying" and not entry.dying then
            entry.dying = true
            entity:SetAttribute("Damageable", false)
            NpcCombatAIService.Unbind(entity)
            presentation.BeginDeath()
        end
    end)
    entity.Destroying:Connect(function()
        -- External removals still schedule a single replacement at the same point.
        if state.instances[entity] == entry then
            release(state, entity, true)
        end
    end)
    return true
end

local function fill(state: any)
    if not state.active or state.filling then
        return
    end
    state.filling = true
    -- Exactly one living/dying NPC per authored spawn record. Legacy
    -- maxAlive/spawnRadius values from older manifests are ignored.
    if next(state.instances) == nil then
        spawnOne(state)
    end
    state.filling = false
end

function NpcSpawnerService.Start()
    if started then
        return
    end
    started = true
    NpcCombatAIService.Start()
    folder()
    local authoring = Workspace:FindFirstChild("Game1Authoring")
    local markers = authoring and authoring:FindFirstChild("NpcSpawns")
    if markers then
        markers:Destroy()
    end
    RunService.PreAnimation:Connect(function(delta)
        for _, state in pairs(states) do
            for entity, entry in pairs(state.instances) do
                if entry.presentation.Step(delta) and entry.dying then
                    entity:SetAttribute("NpcAnimationState", "death_idle")
                    DeathLifecycleService.BeginDeathIdle(entity, entry.root, entry.visual, function()
                        release(state, entity, true)
                    end)
                end
            end
        end
    end)
    local count = 0
    for _, record in ipairs(NpcSpawnRegistry.records or {}) do
        local placeId = math.floor(finite(record.placeId, 0))
        if record.enabled ~= false and (placeId == 0 or game.PlaceId == 0 or placeId == game.PlaceId) then
            local state = { record = record, active = true, filling = false, instances = {} }
            state.fill = function() fill(state) end
            states[tostring(record.spawnId or count + 1)] = state
            fill(state)
            count += 1
        end
    end
    print(("[game1][npc] %d spawn record(s) active"):format(count))
end

return table.freeze(NpcSpawnerService)
