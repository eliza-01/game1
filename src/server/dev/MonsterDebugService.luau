local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local MonsterDebugService = {}
local started = false

local function ensureRemoteFolder(): Folder
    local folder = ReplicatedStorage:FindFirstChild("Game1Remotes")
    if folder and folder:IsA("Folder") then return folder end
    if folder then folder:Destroy() end
    folder = Instance.new("Folder")
    folder.Name = "Game1Remotes"
    folder.Parent = ReplicatedStorage
    return folder
end

local function ensureRemoteFunction(parent: Instance, name: string): RemoteFunction
    local current = parent:FindFirstChild(name)
    if current and current:IsA("RemoteFunction") then return current end
    if current then current:Destroy() end
    local remote = Instance.new("RemoteFunction")
    remote.Name = name
    remote.Parent = parent
    return remote
end

local function finite(value: any, fallback: number): number
    local n = tonumber(value)
    if n == nil or n ~= n or n == math.huge or n == -math.huge then return fallback end
    return n
end

local function collect(): {Model}
    local result = {}
    local folder = Workspace:FindFirstChild("Monsters")
    if not folder then return result end
    for _, child in ipairs(folder:GetChildren()) do
        if child:IsA("Model") and child:GetAttribute("Game1MonsterRuntime") == true then table.insert(result, child) end
    end
    table.sort(result, function(a, b)
        local al = tostring(a:GetAttribute("MonsterSlug") or a.Name) .. tostring(a:GetAttribute("MonsterInstanceId") or "")
        local bl = tostring(b:GetAttribute("MonsterSlug") or b.Name) .. tostring(b:GetAttribute("MonsterInstanceId") or "")
        return al < bl
    end)
    return result
end

local function idOf(model: Model): string
    return tostring(model:GetAttribute("MonsterInstanceId") or model.Name)
end

local function find(id: any): Model?
    local wanted = tostring(id or "")
    for _, model in ipairs(collect()) do if idOf(model) == wanted then return model end end
    return nil
end

local function row(model: Model): any
    local id = idOf(model)
    local short = #id > 8 and id:sub(-8) or id
    return {
        id = id,
        label = string.format("%s · %s", tostring(model:GetAttribute("MonsterSlug") or model.Name), short),
        model = model,
        aggressive = model:GetAttribute("MonsterAggressive") == true,
        aggroRadius = math.max(0, finite(model:GetAttribute("MonsterAggroRadius"), 16)),
        attackRadius = math.max(0, finite(model:GetAttribute("MonsterAttackRadius"), 3)),
        authoredAggressive = model:GetAttribute("MonsterAuthoredAggressive") == true,
        authoredAggroRadius = math.max(0, finite(model:GetAttribute("MonsterAuthoredAggroRadius"), 16)),
        authoredAttackRadius = math.max(0, finite(model:GetAttribute("MonsterAuthoredAttackRadius"), 3)),
        aiState = tostring(model:GetAttribute("MonsterAIState") or "Idle"),
        targetName = tostring(model:GetAttribute("MonsterTargetName") or ""),
        lifeState = tostring(model:GetAttribute("LifeState") or "Alive"),
    }
end

local function catalog(_player: Player)
    local rows = {}
    for _, model in ipairs(collect()) do table.insert(rows, row(model)) end
    return { monsters = rows, selectedId = rows[1] and rows[1].id or "" }
end

local function apply(_player: Player, id: any, patch: any)
    local model = find(id)
    if not model then return {ok = false, error = "selected monster no longer exists"} end
    if type(patch) ~= "table" then return {ok = false, error = "monster debug patch must be a table"} end
    if patch.reset == true then
        model:SetAttribute("MonsterAggressive", model:GetAttribute("MonsterAuthoredAggressive") == true)
        model:SetAttribute("MonsterAggroRadius", math.max(0, finite(model:GetAttribute("MonsterAuthoredAggroRadius"), 16)))
        model:SetAttribute("MonsterAttackRadius", math.max(0, finite(model:GetAttribute("MonsterAuthoredAttackRadius"), 3)))
    else
        if patch.aggressive ~= nil then model:SetAttribute("MonsterAggressive", patch.aggressive == true) end
        if patch.aggroRadius ~= nil then model:SetAttribute("MonsterAggroRadius", math.clamp(finite(patch.aggroRadius, 16), 0, 10000)) end
        if patch.attackRadius ~= nil then model:SetAttribute("MonsterAttackRadius", math.clamp(finite(patch.attackRadius, 3), 0, 10000)) end
    end
    return {ok = true, monster = row(model)}
end

function MonsterDebugService.Start()
    if started or not RunService:IsStudio() then return end
    started = true
    local remotes = ensureRemoteFolder()
    ensureRemoteFunction(remotes, "GetMonsterDebugCatalog").OnServerInvoke = catalog
    ensureRemoteFunction(remotes, "ApplyMonsterDebug").OnServerInvoke = apply
    print("[game1][monster-debug] runtime aggro/radius tuning ready")
end

return table.freeze(MonsterDebugService)
