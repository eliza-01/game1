-- M342: remove retired COL geometry from pasted/placed managed Real Estates.
-- No physics restoration or legacy collision mode remains.
-- One event-driven pass per newly inserted managed root; no Workspace polling.
local Cleanup = require(script.Parent.StudioRetiredColMeshCleanup)
local PlacedTargets = require(script.Parent.StudioRealEstatePlacedTargets)
local Guard = {}

function Guard.Start(Workspace: any, RunService: any): () -> ()
    local pending = setmetatable({}, {__mode = "k"})
    local enabled = true

    local function onAdded(instance: Instance)
        if not enabled or RunService:IsRunning() or not instance:IsA("Model") then
            return
        end
        local slug = instance:GetAttribute("Game1RealEstateSlug")
        if typeof(slug) ~= "string" or slug == "" or pending[instance] then
            return
        end
        -- A nested managed model is not another house. The attribute belongs
        -- to the top-level template/placed root, not its individual rigs.
        local ancestor = instance.Parent
        while ancestor and ancestor ~= Workspace do
            if ancestor:IsA("Model") and ancestor:GetAttribute("Game1RealEstateSlug") == slug then
                return
            end
            ancestor = ancestor.Parent
        end
        pending[instance] = true
        task.delay(0.1, function()
            pending[instance] = nil
            if not enabled or RunService:IsRunning() or not instance:IsDescendantOf(Workspace) then
                return
            end
            local removed = Cleanup.CleanEstate(instance)
            PlacedTargets.MarkPlaced(instance)
            if removed > 0 then
                print(("[game1 plugin] removed %d retired COL mesh(es) from %s")
                    :format(removed, instance:GetFullName()))
            end
        end)
    end

    local connection = Workspace.DescendantAdded:Connect(onAdded)
    -- Also repair copies that were placed before the plugin was installed or
    -- reloaded. This scan runs once on plugin startup, not on every frame.
    for _, instance in Workspace:GetDescendants() do
        onAdded(instance)
    end
    return function()
        enabled = false
        connection:Disconnect()
    end
end

return table.freeze(Guard)
