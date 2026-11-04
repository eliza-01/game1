-- Applied only to initial decoration placement. Studio Sync never changes
-- physical-part policy or replaces already placed geometry.
local DecoAssetPreparation = {}

function DecoAssetPreparation.PreparePlaced(model: Model)
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("BasePart") then
            -- The placement ghost is anchored; placed decorations are not.
            -- Collision and query properties remain authored by the model.
            descendant.Anchored = false
            descendant.CanTouch = false
        end
    end
end

return table.freeze(DecoAssetPreparation)
