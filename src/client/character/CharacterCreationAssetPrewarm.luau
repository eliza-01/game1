--!strict
-- Best-effort background warm AFTER real bootstrap previews are ready.
-- Foreground preview requests never wait for this optional remote or queue.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Request = require(script.Parent:WaitForChild("CharacterCreationRequest"))
local Preloader = require(script.Parent:WaitForChild("CharacterCreationMeshPreloader"))
local Warm = {}
function Warm.Run(remote: RemoteFunction, current: () -> boolean): boolean
    local deadline = os.clock() + 20
    local function alive(): boolean return current() and os.clock() < deadline end
    local complete = true
    for index = 1, 24 do
        if not alive() then return false end
        local ok, response = Request.Invoke(remote, alive, 10, index)
        if not alive() then return false end
        if not ok or type(response) ~= "table" or response.ok ~= true then
            warn("[game1][character-creation] optional component warm incomplete: " .. tostring(if type(response) == "table" then response.error else response))
            return false
        end
        if response.done then return complete end
        local sources: {MeshPart} = {}
        local replicaDeadline = math.min(deadline, os.clock() + 5)
        for _, name in ipairs(response.meshes) do
            local source: Instance? = nil
            repeat
                local folder = ReplicatedStorage:FindFirstChild("Game1CharacterWarmSources")
                source = folder and folder:FindFirstChild(name)
                if source and source:IsA("MeshPart") and source.MeshId ~= "" then break end
                if not alive() or os.clock() >= replicaDeadline then return false end
                task.wait(0.05)
            until false
            table.insert(sources, source :: MeshPart)
        end
        local loaded = Preloader.PreloadResources(sources, response.images, alive)
        complete = complete and loaded
        if index >= response.count then return complete end
    end
    return false
end
return table.freeze(Warm)
