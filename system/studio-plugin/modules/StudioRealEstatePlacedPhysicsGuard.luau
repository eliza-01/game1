-- Studio Edit Mode: normalize a managed Estate pasted or dragged from
-- ServerStorage into Workspace. The normal Sync path already normalizes its
-- staged MeshParts; manual copy/paste does not call that path.
-- One event-driven pass per newly inserted managed root; no Workspace polling.
local CollisionPolicy = require(script.Parent.StudioRealEstateCollisionPolicy)
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
            local restored = 0
            for _, descendant in instance:GetDescendants() do
                if descendant:IsA("MeshPart") then
                    if CollisionPolicy.RestoreCopiedMesh(descendant) then
                        restored += 1
                    end
                end
            end
            -- Cloned ServerStorage templates must not masquerade as templates
            -- once they are placed in Workspace.
            PlacedTargets.MarkPlaced(instance)
            if restored > 0 then
                print(("[game1 plugin] repaired %d copied Estate MeshPart physics settings: %s")
                    :format(restored, instance:GetFullName()))
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
