--!strict
-- No physical collisions needed: moving local player + indexed tree/bush bounds.
-- Local-only, bounded, recycled MeshParts; no per-leaf network replication.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Options = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("GameOptionsRegistry"))
local Index = require(script.Parent:WaitForChild("FloraContactIndex"))
local Pool = require(script.Parent:WaitForChild("FloraLeafPool"))
local Controller = {}
local started = false
local random = Random.new()
local config = Options.flora or {}
local active: {any} = {}
local lastContact = -math.huge
local sampleElapsed, drawElapsed = 0, 0
local lastPosition: Vector3? = nil
local function rootPart(): BasePart?
    local char = Players.LocalPlayer.Character
    if not char then return nil end
    local root = char:FindFirstChild("RootCollider") or char:FindFirstChild("HumanoidRootPart")
        or char:FindFirstChild("NavigationRoot")
    return if root and root:IsA("BasePart") then root else nil
end
local function randomDisc(radius: number): Vector3
    local a = random:NextNumber(0, 2 * math.pi)
    local r = math.sqrt(random:NextNumber()) * radius
    return Vector3.new(math.cos(a)*r, 0, math.sin(a)*r)
end
local function emit(contact: Vector3, movement: Vector3)
    local duration = config.durationSeconds or 1.5
    local spawnRadius = config.spawnRadiusStuds or 2
    local spread = config.spreadRadiusStuds or 5
    for _ = 1, (config.leavesPerBurst or 8) do
        local part = Pool.Acquire()
        if not part then break end -- hard cap, never instantiate in a burst
        local drift = randomDisc(1)
        local movementHorizontal = Vector3.new(movement.X, 0, movement.Z)
        local direction = drift + (if movementHorizontal.Magnitude > 0.05
            then movementHorizontal.Unit * 0.4 else Vector3.zero)
        if direction.Magnitude < 0.01 then direction = Vector3.xAxis end
        local position = contact + Vector3.new(0, 1.2, 0) + randomDisc(spawnRadius)
        local scale = random:NextNumber(0.7, 1.2)
        local size = part.Size
        part.Size = size * scale
        part.CFrame = CFrame.new(position)
        table.insert(active, {
            part = part, origin = position, direction = direction.Unit,
            distance = spread * random:NextNumber(0.6, 1.1),
            duration = duration * random:NextNumber(0.85, 1.15),
            age = 0,
            lift = random:NextNumber(1.1, 2.2),
            fall = random:NextNumber(0.2, 1.2),
            spin = random:NextNumber(-8, 8),
            angle = random:NextNumber(-math.pi, math.pi),
            tilt = random:NextNumber(-math.pi, math.pi),
        })
    end
end
local function render(dt: number)
    -- Advance at 30Hz while effect is active; low-end mobile never runs 60
    -- particle updates per second, and zero work is done when the pool is idle.
    if #active == 0 then drawElapsed = 0; return end
    drawElapsed += dt
    if drawElapsed < 1 / 30 then return end
    local step = math.min(drawElapsed, 0.12)
    drawElapsed = 0
    for i = #active, 1, -1 do
        local item = active[i]
        item.age += step
        local t = math.min(1, item.age / item.duration)
        if t >= 1 then
            Pool.Release(item.part)
            table.remove(active, i)
        else
            local horizontal = item.direction * item.distance * (t ^ 0.85)
            local vertical = 4 * item.lift * t * (1 - t) - item.fall * t
            local pos = item.origin + horizontal + Vector3.new(0, vertical, 0)
            item.part.CFrame = CFrame.new(pos) * CFrame.Angles(item.tilt + t*item.spin, item.angle + t*2.5, t*item.spin*0.7)
            item.part.LocalTransparencyModifier = math.clamp((t - 0.7) / 0.3, 0, 1)
        end
    end
end
local function sample(dt: number)
    sampleElapsed += dt
    if sampleElapsed < 0.12 then return end
    sampleElapsed = 0
    local root = rootPart()
    if not root then lastPosition = nil; return end
    local position = root.Position
    local previous = lastPosition
    lastPosition = position
    if not previous then return end
    local movement = position - previous
    -- Standing in vegetation is not continuous 'collision'. Avoid spawn-in
    -- effects and teleportation streaks; only actual walking generates leaves.
    if movement.Magnitude < 0.25 or movement.Magnitude > 12 then return end
    local now = os.clock()
    if now - lastContact < (config.cooldownSeconds or 1.5) then return end
    -- Contact around waist level with the actual rotated geometry bounds,
    -- not the origin/pivot of the entire tree (often underground).
    local model, contact = Index.Find(position + Vector3.new(0, 1.5, 0), config.contactPaddingStuds or 1.25)
    if (not model or not contact) and movement.Magnitude > 1 then
        -- A player may cross a thin bush between two 120 ms samples.
        model, contact = Index.Find((position + previous) * 0.5 + Vector3.new(0, 1.5, 0),
            config.contactPaddingStuds or 1.25)
    end
    if not model or not contact then return end
    lastContact = now -- global cap, including simultaneous overlapping plants
    emit(contact, movement)
end
function Controller.Start()
    if started then return end
    started = true
    if config.enabled ~= true then return end
    local slug = config.leafAssetSlug
    if type(slug) ~= "string" then return end
    task.spawn(function()
        if not Pool.Start(slug, math.clamp(config.maxActiveLeaves or 32, 8, 96)) then
            warn("[game1][flora] VFX disabled: leaf asset unavailable")
            return
        end
        Index.Start()
        RunService.Heartbeat:Connect(function(dt)
            sample(dt)
            render(dt)
        end)
        print("[game1][flora] local leaf pool ready: " .. slug)
    end)
end
return table.freeze(Controller)
