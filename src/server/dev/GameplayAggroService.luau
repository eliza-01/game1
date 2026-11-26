-- Studio-only species tuning. The authenticated local plugin persists explicit Sync requests.
local RS = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local HttpService = game:GetService("HttpService")
local Shared = RS:WaitForChild("Game1Shared")
local Balance = require(Shared:WaitForChild("balance"):WaitForChild("Balance"))
local Access = require(Shared:WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local Overrides = require(script.Parent:WaitForChild("GameplayAggroOverrides"))
local Service = {}
local started = false
local function allowed(player)
    return RunService:IsStudio() and Access.ServerAllowed(player) and player:GetAttribute("Game1GameplayTestActive") == true
end
local species = {}
for _, row in ipairs(Balance.Monsters) do
    if row.nameEn ~= "" then species[row.nameEn] = row end
end
local function validRadius(value)
    return type(value)=="number" and value==value and value>=0 and value<=10000
end
function Service.Start()
    if started or not RunService:IsStudio() then return end
    started = true
    local remotes = RS:WaitForChild("Game1Remotes")
    local remote = Instance.new("RemoteFunction")
    remote.Name = "SyncGameplayAggro"; remote.Parent = remotes
    local folder = Instance.new("Folder")
    folder.Name = "Game1GameplayAggroSync"; folder.Parent = RS
    local last = 0
    remote.OnServerInvoke = function(player, request)
        if not allowed(player) then return {ok=false,error="Enter GP first"} end
        if type(request)~="table" or #request<1 or #request>70 or os.clock()-last<1 then return {ok=false,error="Invalid request / retry in 1s"} end
        local checked, seen = {}, {}
        for _, entry in ipairs(request) do
            if type(entry)~="table" or type(entry.nameEn)~="string" or not species[entry.nameEn] or seen[entry.nameEn]
                or not validRadius(entry.radius) or not validRadius(entry.oldRadius)
                or type(entry.aggressive)~="boolean" or type(entry.oldAggressive)~="boolean" then
                return {ok=false,error="Invalid species settings"}
            end
            seen[entry.nameEn]=true
            table.insert(checked,{nameEn=entry.nameEn, radius=entry.radius, aggressive=entry.aggressive, oldRadius=entry.oldRadius, oldAggressive=entry.oldAggressive})
        end
        last=os.clock()
        -- Live testing is separate from persistence; plugin sends an explicit receipt.
        for _, entry in ipairs(checked) do Overrides.Set(entry.nameEn,entry.radius,entry.aggressive) end
        local monsters=workspace:FindFirstChild("Monsters")
        if monsters then for _, model in ipairs(monsters:GetChildren()) do
            if model:IsA("Model") and model:GetAttribute("Game1GameplayTestOwner")==player.UserId and model:GetAttribute("GameplayTestKind")=="zone" and (tonumber(model:GetAttribute("GameplayTestZone")) or 99)<=6 then
                local change=Overrides.Get(tostring(model:GetAttribute("MonsterNameEn") or ""))
                if change then
                    model:SetAttribute("MonsterAggroRadius",change.radius); model:SetAttribute("MonsterAuthoredAggroRadius",change.radius)
                    model:SetAttribute("MonsterAggressive",change.aggressive); model:SetAttribute("MonsterAuthoredAggressive",change.aggressive)
                end
            end
        end end
        local nonce=HttpService:GenerateGUID(false)
        folder:SetAttribute("Payload",HttpService:JSONEncode({changes=checked,nonce=nonce}))
        return {ok=true,nonce=nonce}
    end
end
return table.freeze(Service)
