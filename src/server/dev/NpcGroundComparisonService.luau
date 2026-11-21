-- Studio-only, read-only ground clearance comparison for two NPC species.
-- Remove this temporary probe once the guard_02 grounding regression is fixed.
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local Players = game:GetService("Players")
local HttpService = game:GetService("HttpService")

local Service = {}
local started = false
local WANTED_PLAYER = "kitiket322322"
local WANTED_NAMES = {guard_01 = "guard_01_711887", guard_02 = "guard_02_520666"}
local ORDER = {"guard_01", "guard_02"}
local SAMPLE_STEP = 0.2
local MAX_SECONDS = 240
local rows = {}
local stateByModel = {}
local begun = nil

local function rounded(value: number?): number?
    if value == nil or value ~= value or value == math.huge or value == -math.huge then return nil end
    return math.round(value * 1000) / 1000
end

local function targetPlayer(): Player?
    for _, player in ipairs(Players:GetPlayers()) do
        if string.lower(player.Name) == WANTED_PLAYER then return player end
    end
    return nil
end

local function identify(model: Model): string?
    local slug = tostring(model:GetAttribute("NpcSlug") or "")
    if WANTED_NAMES[slug] then return slug end
    for _, wanted in ipairs(ORDER) do
        if model.Name:sub(1, #wanted + 1) == wanted .. "_" then return wanted end
    end
    return nil
end

local function findActors(player: Player?): {[string]: Model}
    local folder = Workspace:FindFirstChild("NPCs")
    local chosen = {}
    local score = {}
    if not folder then return chosen end
    local playerRoot = player and player.Character and player.Character:FindFirstChild("HumanoidRootPart")
    for _, child in ipairs(folder:GetChildren()) do
        if child:IsA("Model") and child:GetAttribute("LifeState") == "Alive" then
            local slug = identify(child)
            if slug then
                local root = child:FindFirstChild("HumanoidRootPart")
                if root and root:IsA("BasePart") then
                    local priority = if child.Name == WANTED_NAMES[slug] then -100000
                        elseif playerRoot and playerRoot:IsA("BasePart") then (root.Position - playerRoot.Position).Magnitude
                        else 0
                    if score[slug] == nil or priority < score[slug] then
                        score[slug] = priority
                        chosen[slug] = child
                    end
                end
            end
        end
    end
    return chosen
end

local function groundBelow(model: Model, root: BasePart, player: Player?): (number?, string)
    local exclusions: {Instance} = {model}
    if player and player.Character then table.insert(exclusions, player.Character) end
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = exclusions
    params.IgnoreWater = true
    local origin = root.Position + Vector3.new(0, 5, 0)
    local hit = Workspace:Raycast(origin, Vector3.new(0, -40, 0), params)
    return if hit then hit.Position.Y else nil, if hit then hit.Instance:GetFullName() else "none"
end

local function visibleBottom(model: Model): (number?, number)
    local visual = model:FindFirstChild("ImportedRig")
    if not visual or not visual:IsA("Model") then visual = model end
    local low = math.huge
    local count = 0
    for _, part in ipairs(visual:GetDescendants()) do
        if part:IsA("MeshPart") and part.Name ~= "RootCollider" and part.Name ~= "HumanoidRootPart" then
            count += 1
            local half = part.Size * 0.5
            for dx = -1, 1, 2 do
                for dy = -1, 1, 2 do
                    for dz = -1, 1, 2 do
                        local at = part.CFrame:PointToWorldSpace(Vector3.new(dx * half.X, dy * half.Y, dz * half.Z))
                        low = math.min(low, at.Y)
                    end
                end
            end
        end
    end
    return if count > 0 then low else nil, count
end

local function spineOffset(model: Model, root: BasePart): number?
    for _, item in ipairs(model:GetDescendants()) do
        if item:IsA("Bone") then
            local name = string.lower(item.Name)
            if name == "spine" or name == "pelvis" or name == "hips" then
                local ok, position = pcall(function()
                    return item.TransformedWorldCFrame.Position
                end)
                if ok then return rounded(position.Y - root.Position.Y) end
                return rounded(item.WorldCFrame.Position.Y - root.Position.Y)
            end
        end
    end
    return nil
end

local function playingTracks(model: Model): {string}
    local labels = {}
    for _, item in ipairs(model:GetDescendants()) do
        if item:IsA("Animator") then
            for _, track in ipairs(item:GetPlayingAnimationTracks()) do
                local animation = track.Animation
                local label = if animation then animation.AnimationId else track.Name
                table.insert(labels, string.format("%s@%.2f/%.2f", tostring(label), track.TimePosition, track.Speed))
                if #labels >= 4 then return labels end
            end
        end
    end
    return labels
end

local function snapshot(slug: string, model: Model, player: Player?, t: number): any
    local root = model:FindFirstChild("HumanoidRootPart")
    if not root or not root:IsA("BasePart") then return nil end
    local humanoid = model:FindFirstChildOfClass("Humanoid")
    local floorY, groundPart = groundBelow(model, root, player)
    local bottom, meshCount = visibleBottom(model)
    local before = stateByModel[model]
    if not before then
        before = {y = root.Position.Y, first = t, last = -1, state = "", phase = ""}
        stateByModel[model] = before
    end
    local state = tostring(model:GetAttribute("NpcAIState") or "?")
    local phase = tostring(model:GetAttribute("NpcAttackPhase") or "")
    local changed = state ~= before.state or phase ~= before.phase
    if changed then before.state, before.phase, before.transitionAt = state, phase, t end
    local active = state == "Chase" or state == "Attack" or state == "AttackReady" or state == "Aggro"
    local fast = active and (t - (before.transitionAt or t) < 3)
    local every = if fast then 0.2 elseif active then 0.8 else 5
    if not changed and t - before.last < every then return nil end
    before.last = t
    local playerRoot = player and player.Character and player.Character:FindFirstChild("HumanoidRootPart")
    local verticalSpeed = root.AssemblyLinearVelocity.Y
    local item = {
        t = rounded(t), name = model.Name, slug = slug, state = state, phase = phase,
        animationState = tostring(model:GetAttribute("NpcAnimationState") or ""),
        rootY = rounded(root.Position.Y), rootYFromSpawn = rounded(root.Position.Y - before.y),
        groundY = rounded(floorY), rootAboveGround = rounded(if floorY then root.Position.Y - floorY else nil),
        visualBottomAboveGround = rounded(if floorY and bottom then bottom - floorY else nil),
        visualBottomBelowRoot = rounded(if bottom then bottom - root.Position.Y else nil),
        spineAboveRoot = spineOffset(model, root),
        rootVerticalSpeed = rounded(verticalSpeed), rootAnchored = root.Anchored,
        rootCanCollide = root.CanCollide, rootCollisionGroup = root.CollisionGroup,
        humanoidHipHeight = if humanoid then rounded(humanoid.HipHeight) else nil,
        humanoidState = if humanoid then humanoid:GetState().Name else "missing",
        humanoidFloor = if humanoid then humanoid.FloorMaterial.Name else "missing",
        runSpeed = rounded(tonumber(model:GetAttribute("RunSpeed"))),
        attackSpeed = rounded(tonumber(model:GetAttribute("AttackSpeed"))),
        meshParts = meshCount, groundPart = groundPart,
        playerDistance = rounded(if playerRoot and playerRoot:IsA("BasePart") then
            (root.Position - playerRoot.Position).Magnitude else nil),
        tracks = playingTracks(model),
    }
    return item
end

function Service.Start()
    if started or not RunService:IsStudio() then return end
    started = true
    print("[game1][npc-ground] studio probe armed for guard_01, guard_02; player kitiket322322; no gameplay changes")
    local tickTime = 0
    local elapsed = 0
    local connection: RBXScriptConnection?
    connection = RunService.Heartbeat:Connect(function(dt)
        tickTime += dt
        if tickTime < SAMPLE_STEP then return end
        tickTime %= SAMPLE_STEP
        local player = targetPlayer()
        local actors = findActors(player)
        if not begun and (actors.guard_01 or actors.guard_02) then begun = os.clock() end
        if not begun then return end
        elapsed = os.clock() - begun
        if elapsed >= MAX_SECONDS then
            print("[game1][npc-ground] finished: 240 seconds elapsed; send Output lines with prefix [game1][npc-ground]")
            if connection then connection:Disconnect() end
            return
        end
        for _, slug in ipairs(ORDER) do
            local model = actors[slug]
            if model then
                local ok, record = pcall(snapshot, slug, model, player, elapsed)
                if ok and record then
                    rows[slug] = record
                    print("[game1][npc-ground] " .. HttpService:JSONEncode(record))
                elseif not ok then
                    warn("[game1][npc-ground] sampling error for " .. slug .. ": " .. tostring(record))
                end
            end
        end
    end)
end

return table.freeze(Service)
