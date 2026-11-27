--!strict
local ReplicatedStorage=game:GetService("ReplicatedStorage")
local Aura=require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("BuffCastVisuals"))
local Visuals={}
function Visuals.Start()
    task.spawn(function()
        local remotes=ReplicatedStorage:WaitForChild("Game1Remotes")
        local remote=remotes:WaitForChild("MonsterHomeRecallVisual") :: RemoteEvent
        remote.OnClientEvent:Connect(function(foot: Vector3,height: number,radius: number)
            Aura.PlayAt(foot,Color3.fromRGB(185,150,255),height,radius)
        end)
    end)
end
return table.freeze(Visuals)
