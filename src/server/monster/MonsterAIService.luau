-- Server-authoritative monster combat AI adapted from RobloxLineage.
-- Contract: Aggro -> Chase -> Attack. While an authored attack is still active,
-- a target that leaves weapon range is pursued directly without cancelling the
-- attack; the live target position is validated again on the Hit timeline event.
local Workspace = game:GetService("Workspace")

local Facing = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("ActorFacingTracker"))
local TargetPolicy = require(script.Parent:WaitForChild("MonsterTargetPolicy"))
local CombatState = require(script.Parent:WaitForChild("MonsterCombatState"))
local Presentation = require(script.Parent:WaitForChild("MonsterCombatPresentation"))
local AttackExecutor = require(script.Parent:WaitForChild("MonsterAttackExecutor"))
local Navigation = require(script.Parent:WaitForChild("MonsterChaseNavigation"))

local MonsterAIService = {}
local started = false
local agents: {[Model]: any} = {}
local random = Random.new()

local THINK_INTERVAL = 0.10
local TARGET_SCAN_INTERVAL = 0.30
local rootOf = TargetPolicy.RootOf
local navigationRootOf = TargetPolicy.NavigationRootOf
local targetIsValid = TargetPolicy.IsValid
local horizontalDistance = TargetPolicy.HorizontalDistance
local aggressive = TargetPolicy.IsAggressive
local attackRadius = TargetPolicy.AttackRadius

local setState = CombatState.SetState

-- Movement and its per-agent path/blocked state are owned by MonsterChaseNavigation.
local clearPath = Navigation.ClearPath
local stopNavigation = Navigation.StopNavigation
local runSpeedStuds = Navigation.RunSpeedStuds
local navigateTo = Navigation.NavigateTo

local AttackMovement = table.freeze({
    StopNavigation = stopNavigation,
    RunSpeedStuds = runSpeedStuds,
})

local function leaveCombat(agent: any)
    Facing.Stop(agent.model)
    CombatState.ClearTarget(agent)
    agent.attacking = false
    agent.attackSerial += 1
    AttackExecutor.ClearPursuit(agent)
    stopNavigation(agent)
    Presentation.Stop(agent)
    CombatState.FinishExit(agent)
end

local function updateTarget(agent: any, now: number)
    if agent.target and targetIsValid(agent.target) then return end
    if agent.target then leaveCombat(agent) end
    if not aggressive(agent) or now < agent.nextTargetScanAt then return end
    agent.nextTargetScanAt = now + TARGET_SCAN_INTERVAL
    local target = TargetPolicy.AcquireNearestTarget(agent)
    if target then CombatState.Enter(agent, target) end
end

local function runAgent(agent: any)
    task.wait(random:NextNumber(0, THINK_INTERVAL))
    while agent.active and agent.model.Parent do
        task.wait(THINK_INTERVAL)
        if tostring(agent.model:GetAttribute("LifeState") or "") ~= "Alive" then
            leaveCombat(agent)
            break
        end
        -- The rig can be temporarily anchored below terrain during spawn reveal.
        if agent.model:GetAttribute("MonsterSpawning") == true then
            continue
        end
        if not aggressive(agent) then
            if agent.target or agent.model:GetAttribute("MonsterCombatActive") == true then leaveCombat(agent) end
            continue
        end
        local now = os.clock()
        updateTarget(agent, now)
        local target = agent.target
        local targetRoot = rootOf(target)
        local distance = if targetRoot then horizontalDistance(agent.root.Position, targetRoot.Position) else 0
        local action = CombatState.Decide(agent.attacking, targetRoot ~= nil, distance, attackRadius(agent))
        if action == "AttackActive" then
            -- Active-attack movement is owned by maintainAttackPursuit().
            -- The slower AI decision loop must not issue competing MoveTo calls.
            setState(agent, "Attack")
        elseif action == "BeginAttack" then
            stopNavigation(agent)
            AttackExecutor.FaceDirection(agent, targetRoot.Position - agent.root.Position)
            Presentation.PlayCombatIdle(agent)
            AttackExecutor.Begin(agent, target, AttackMovement, random)
        elseif action == "Chase" then
            setState(agent, "Chase")
            AttackExecutor.ClearPursuit(agent)
            Presentation.PlayRun(agent)
            navigateTo(agent, targetRoot.Position, runSpeedStuds(agent))
        elseif agent.model:GetAttribute("MonsterCombatActive") == true then
            leaveCombat(agent)
        end
    end
    agent.active = false
    CombatState.ClearPursuit(agent)
end

local function bindMonster(model: Model)
    if agents[model] then return end
    task.spawn(function()
        local deadline = os.clock() + 5
        while model.Parent and model:GetAttribute("Game1MonsterRuntime") ~= true and os.clock() < deadline do
            task.wait(0.03)
        end
        if not model.Parent or model:GetAttribute("Game1MonsterRuntime") ~= true or agents[model] then return end
        local root = navigationRootOf(model) or model:WaitForChild("HumanoidRootPart", 5)
        local humanoid = model:FindFirstChildOfClass("Humanoid") or model:WaitForChild("Humanoid", 5)
        local animator = Presentation.AnimatorOf(model)
        if not root or not root:IsA("BasePart") or not humanoid or not humanoid:IsA("Humanoid") or not animator then return end
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
        model:GetAttributeChangedSignal("LifeState"):Connect(function()
            if agents[model] == agent and tostring(model:GetAttribute("LifeState") or "") ~= "Alive" then
                agent.attackSerial += 1
                Facing.Stop(agent.model)
                agent.attacking = false
                CombatState.ClearTarget(agent)
                AttackExecutor.ClearPursuit(agent)
                stopNavigation(agent)
                Presentation.Stop(agent)
                model:SetAttribute("MonsterCombatActive", false)
            end
        end)
        model.Destroying:Connect(function()
            if agents[model] == agent then
                agent.active = false
                CombatState.ClearPursuit(agent)
                Facing.Stop(agent.model)
                clearPath(agent)
                agents[model] = nil
            end
        end)
        task.spawn(runAgent, agent)
    end)
end

local function bindFolder(folder: Folder)
    for _, child in ipairs(folder:GetChildren()) do if child:IsA("Model") then bindMonster(child) end end
    folder.ChildAdded:Connect(function(child) if child:IsA("Model") then task.defer(bindMonster, child) end end)
end

function MonsterAIService.Start()
    if started then return end
    started = true
    local folder = Workspace:FindFirstChild("Monsters")
    if folder and folder:IsA("Folder") then bindFolder(folder) end
    Workspace.ChildAdded:Connect(function(child)
        if child.Name == "Monsters" and child:IsA("Folder") then bindFolder(child) end
    end)
    print("[game1][monster-ai] RobloxLineage aggro/chase/attack-pursuit runtime ready")
end

return table.freeze(MonsterAIService)
