-- Owns Monster AI agent discovery, initialization, per-model signals and teardown.
-- Attack decisions, target policy, chase, and authored attack pursuit stay outside.
local Workspace = game:GetService("Workspace")
local Facing = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("ActorFacingTracker"))
local CombatState = require(script.Parent:WaitForChild("MonsterCombatState"))
local Presentation = require(script.Parent:WaitForChild("MonsterCombatPresentation"))
local AttackExecutor = require(script.Parent:WaitForChild("MonsterAttackExecutor"))
local Navigation = require(script.Parent:WaitForChild("MonsterChaseNavigation"))
local TargetPolicy = require(script.Parent:WaitForChild("MonsterTargetPolicy"))

local MonsterAgentLifecycle = {}
local agents: {[Model]: any} = {}
local pending: {[Model]: boolean} = {}
local watchedFolders: {[Folder]: {RBXScriptConnection}} = {}
local started = false
local navigationRootOf = TargetPolicy.NavigationRootOf

local function releaseAgent(agent: any)
    local model = agent.model
    if agents[model] ~= agent then return end
    agents[model] = nil
    agent.active = false
    agent.attackSerial += 1 -- Invalidate delayed Hit and attack-finish callbacks.
    for _, connection in ipairs(agent.lifecycleConnections or {}) do
        connection:Disconnect()
    end
    agent.lifecycleConnections = nil
    CombatState.ClearTarget(agent)
    AttackExecutor.ClearPursuit(agent)
    Facing.Stop(model)
    Navigation.ClearPath(agent)
    Presentation.Stop(agent)
end

local function stopOnDeath(agent: any)
    local model = agent.model
    if agents[model] ~= agent or tostring(model:GetAttribute("LifeState") or "") == "Alive" then return end
    agent.attackSerial += 1
    Facing.Stop(model)
    agent.attacking = false
    CombatState.ClearTarget(agent)
    AttackExecutor.ClearPursuit(agent)
    Navigation.StopNavigation(agent)
    Presentation.Stop(agent)
    model:SetAttribute("MonsterCombatActive", false)
end

local function registerModel(model: Model, random: Random, runAgent: (any) -> ())
    if agents[model] or pending[model] then return end
    pending[model] = true
    task.spawn(function()
        local ok, err = xpcall(function()
            local deadline = os.clock() + 5
            while model.Parent and model:GetAttribute("Game1MonsterRuntime") ~= true and os.clock() < deadline do
                task.wait(0.03)
            end
            if not model:IsDescendantOf(Workspace) or model:GetAttribute("Game1MonsterRuntime") ~= true or agents[model] then
                return
            end
            local root = navigationRootOf(model) or model:WaitForChild("HumanoidRootPart", 5)
            local humanoid = model:FindFirstChildOfClass("Humanoid") or model:WaitForChild("Humanoid", 5)
            local animator = Presentation.AnimatorOf(model)
            if not root or not root:IsA("BasePart") or not humanoid or not humanoid:IsA("Humanoid") or not animator or not model:IsDescendantOf(Workspace) then
                return
            end
            local slug = string.lower(tostring(model:GetAttribute("MonsterSlug") or ""))
            local runRow = Presentation.PublishedRows(slug, "run")[1] or Presentation.PublishedRows(slug, "walk")[1]
            local combatIdleRow = Presentation.PublishedRows(slug, "combat_idle")[1] or Presentation.PublishedRows(slug, "idle")[1]
            local attackRows = Presentation.PublishedRows(slug, "attack")
            if #attackRows == 0 then
                warn("[game1][monster-ai] no published attack animation for " .. slug)
            end
            local agent = {
                model = model,
                root = root,
                humanoid = humanoid,
                animator = animator,
                attackRows = attackRows,
                runTrack = runRow and Presentation.LoadTrack(animator, runRow, true) or nil,
                combatIdleTrack = combatIdleRow and Presentation.LoadTrack(animator, combatIdleRow, true) or nil,
                attackTrack = nil,
                target = nil,
                active = true,
                attacking = false,
                attackSerial = 0,
                attackEndsAt = 0,
                nextAttackAt = 0,
                nextTargetScanAt = 0,
                attackPursuitActive = false,
                attackPursuit = AttackExecutor.NewPursuit(root, humanoid),
                facing = root.CFrame.LookVector,
                state = "Idle",
            }
            Navigation.Initialize(agent)
            agents[model] = agent
            Presentation.Initialize(agent, runRow, random, AttackExecutor.PursuitSpeedMultiplier)
            model:SetAttribute("MonsterAttackPursuitActive", false)
            model:SetAttribute("MonsterAIState", "Idle")
            agent.lifecycleConnections = {
                model:GetAttributeChangedSignal("LifeState"):Connect(function()
                    stopOnDeath(agent)
                end),
                model.Destroying:Connect(function()
                    releaseAgent(agent)
                end),
                model.AncestryChanged:Connect(function()
                    if not model:IsDescendantOf(Workspace) then releaseAgent(agent) end
                end),
            }
            task.spawn(function()
                local ok, err = xpcall(runAgent, debug.traceback, agent)
                releaseAgent(agent) -- Also release if the AI loop throws.
                if not ok then warn("[game1][monster-ai] agent loop failed: " .. tostring(err)) end
            end)
        end, debug.traceback)
        pending[model] = nil
        if not ok then
            local agent = agents[model]
            if agent then releaseAgent(agent) end
            warn("[game1][monster-ai] agent registration failed: " .. tostring(err))
        end
    end)
end

local function unwatchFolder(folder: Folder)
    local connections = watchedFolders[folder]
    if not connections then return end
    watchedFolders[folder] = nil
    for _, connection in ipairs(connections) do connection:Disconnect() end
    -- Folder may be detached without destroying its children.
    local toRelease = {}
    for model, agent in pairs(agents) do
        if model:IsDescendantOf(folder) then table.insert(toRelease, agent) end
    end
    for _, agent in ipairs(toRelease) do releaseAgent(agent) end
end

local function watchFolder(folder: Folder, random: Random, runAgent: (any) -> ())
    if watchedFolders[folder] then return end
    watchedFolders[folder] = {
        folder.ChildAdded:Connect(function(child)
            if child:IsA("Model") then task.defer(registerModel, child, random, runAgent) end
        end),
        folder.AncestryChanged:Connect(function()
            if folder.Parent ~= Workspace then unwatchFolder(folder) end
        end),
        folder.Destroying:Connect(function()
            unwatchFolder(folder)
        end),
    }
    for _, child in ipairs(folder:GetChildren()) do
        if child:IsA("Model") then registerModel(child, random, runAgent) end
    end
end

function MonsterAgentLifecycle.Release(agent: any)
    releaseAgent(agent)
end

function MonsterAgentLifecycle.Start(runAgent: (any) -> (), random: Random)
    if started then return end
    started = true
    local folder = Workspace:FindFirstChild("Monsters")
    if folder and folder:IsA("Folder") then watchFolder(folder, random, runAgent) end
    Workspace.ChildAdded:Connect(function(child)
        if child.Name == "Monsters" and child:IsA("Folder") then
            watchFolder(child, random, runAgent)
        end
    end)
end

return table.freeze(MonsterAgentLifecycle)
