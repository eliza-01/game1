local ReplicatedStorage = game:GetService("ReplicatedStorage")

local CombatFloatingText = require(script.Parent:WaitForChild("CombatFloatingText"))

local CombatFeedbackController = {}
local started = false

function CombatFeedbackController.Start()
    if started then
        return
    end
    started = true

    local remote = ReplicatedStorage:WaitForChild("Game1Remotes"):WaitForChild("CombatFeedback")
    if not remote:IsA("RemoteEvent") then
        return
    end

    remote.OnClientEvent:Connect(function(payload: any)
        if type(payload) ~= "table" then return end
        if payload.kind == "miss" or payload.kind == "far" then
            if typeof(payload.position) == "Vector3" then
                if payload.kind == "far" then
                    CombatFloatingText.ShowFar(payload.target, payload.position)
                else
                    CombatFloatingText.ShowMiss(payload.target, payload.position)
                end
            end
            return
        end
        if payload.kind ~= "damage" then return end
        local position = payload.position
        local damage = tonumber(payload.damage) or 0
        if typeof(position) ~= "Vector3" or damage <= 0 then
            return
        end

        local critical = payload.critical == true
        CombatFloatingText.ShowDamage(
            payload.target,
            position,
            damage,
            tostring(payload.relation or "") == "incoming",
            critical
        )
        if critical then
            CombatFloatingText.ShowCritical(payload.target, position)
        end
        if payload.headshot == true then
            CombatFloatingText.ShowHeadshot(payload.target, position)
        end
    end)
end

return table.freeze(CombatFeedbackController)
