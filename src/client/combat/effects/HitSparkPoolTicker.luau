-- Shared on-demand renderer for pooled hit / bounce sparks.
-- No RenderStepped subscription exists while every spark slot is inactive.
local RunService = game:GetService("RunService")
local HitSparkBurst = require(script.Parent:WaitForChild("HitSparkBurst"))

local HitSparkPoolTicker = {}

function HitSparkPoolTicker.Create(slots: {any}): () -> ()
    local connection: RBXScriptConnection? = nil
    return function()
        if connection then return end
        connection = RunService.RenderStepped:Connect(function(dt)
            local active = false
            for _, slot in ipairs(slots) do
                if slot.sparks.active then
                    HitSparkBurst.Step(slot.sparks, dt)
                    if slot.sparks.active then active = true end
                end
            end
            if not active and connection then
                connection:Disconnect()
                connection = nil
            end
        end)
    end
end

return table.freeze(HitSparkPoolTicker)
