-- Only the running DataModel owns this cleanup. Studio Edit retains all
-- authored Location/Monster/NPC markers, metadata, and editable geometry.
-- Spawn data is consumed from published registries, never these preview parts.
local Workspace = game:GetService("Workspace")

local Service = {}
local started = false

local function removeAuthoringRoot(instance: Instance)
    if instance.Name == "Game1Authoring" and instance.Parent == Workspace then
        instance:Destroy()
    end
end

function Service.Start()
    if started then return end
    started = true
    -- Subscribe first, including late additions from Studio tooling.
    Workspace.ChildAdded:Connect(removeAuthoringRoot)
    local root = Workspace:FindFirstChild("Game1Authoring")
    if root then removeAuthoringRoot(root) end
end

return table.freeze(Service)
