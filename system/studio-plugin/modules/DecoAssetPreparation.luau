-- Applied only to initial decoration placement. Studio Sync never changes
-- physical-part policy or replaces already placed geometry.
local MeshPhysics = require(script.Parent.StudioMeshPhysicsCore)
local DecoAssetPreparation = {}

function DecoAssetPreparation.PreparePlaced(model: Model, meshOptions: any?, materialKey: string?, physicalMaterial: string?)
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("BasePart") then
            -- The placement ghost is anchored; placed decorations are not.
            -- Collision and query properties remain authored by the model.
            descendant.Anchored = false
            descendant.CanTouch = false
        end
    end
    -- The policy is reapplied after ghost/preview handling and before Workspace
    -- parenting, without writing any transforms, scale or anchors.
    MeshPhysics.ApplyLocationModel(model, nil, meshOptions)
    MeshPhysics.ApplyLocationSurfaceMaterial(model,materialKey,physicalMaterial)
end

return table.freeze(DecoAssetPreparation)
