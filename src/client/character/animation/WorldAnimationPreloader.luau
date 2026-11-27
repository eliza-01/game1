-- Session-wide content fetch, not playback. No Animator/track per remote actor.
-- All published NPC/monster profiles in this DEV catalog, deduplicated by asset ID.
local ContentProvider = game:GetService("ContentProvider")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Monster = require(Shared:WaitForChild("monster"):WaitForChild("MonsterAnimationRegistry"))
local Npc = require(Shared:WaitForChild("npc"):WaitForChild("NpcAnimationRegistry"))
local Preloader = {}
local started = false
local done = false
local total, ready, completed = 0, 0, 0
local BATCH = 16
local function collect()
    local ids = {}
    for _, registry in ipairs({Monster, Npc}) do
        for _, profile in pairs(registry.profiles or {}) do
            for _, rows in pairs(profile.slots or {}) do
                for _, row in ipairs(rows) do
                    local id = tostring(row.animationId or "")
                    if id:match("^rbxassetid://%d+$") then ids[id] = true end
                end
            end
        end
    end
    local result = {}
    for id in pairs(ids) do table.insert(result, id) end
    table.sort(result)
    return result
end
function Preloader.Start()
    if started then return end
    started = true
    local ids = collect()
    total = #ids
    task.spawn(function()
        local began = os.clock()
        for i = 1, #ids, BATCH do
            local requests = {}
            local successes = {}
            for j = i, math.min(i+BATCH-1, #ids) do
                local animation = Instance.new("Animation")
                animation.AnimationId = ids[j]
                table.insert(requests, animation)
            end
            local ok, err = pcall(function()
                ContentProvider:PreloadAsync(requests, function(asset, status)
                    if status == Enum.AssetFetchStatus.Success then
                        local key = tostring(asset):match("%d+$")
                        if key then successes[key] = true end
                    end
                end)
            end)
            if not ok then warn("[game1][world-animation] preload: " .. tostring(err)) end
            for _, animation in ipairs(requests) do
                local key = animation.AnimationId:match("%d+$")
                if key and successes[key] then ready += 1 end
                completed += 1
                animation:Destroy()
            end
        end
        done = true
        print(("[game1][world-animation] prewarm %d/%d assets in %.3fs"):format(ready,total,os.clock()-began))
        if ready ~= total then warn("[game1][world-animation] incomplete; on-demand engine loading remains enabled") end
    end)
end
function Preloader.Wait(current: () -> boolean, deadline: number, progress: (number) -> ())
    Preloader.Start()
    while current() and not done and os.clock() < deadline do
        progress(if total > 0 then completed / total else 0)
        RunService.Heartbeat:Wait()
    end
    if current() then progress(1) end
    return done and ready == total
end
return table.freeze(Preloader)
