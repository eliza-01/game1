-- Own only resources of one attached presentation generation. Navigation,
-- population and domain pose consumers are deliberately not owned here.
-- The caller MUST quiesce pose consumers and detach combat geometry before Release.
local Lifecycle = {}

function Lifecycle.new(entity, visual, collider, weld, owned, fallbackRootWeld)
    local released = false
    local lease = {}

    -- Equipment is attached at entity level for existing socket consumers.
    -- Register exact instances, never a name/pattern or a subtree scan.
    function lease:OwnEquipment(item)
        assert(not released and item.Parent == entity and item ~= visual and item ~= collider
            and item ~= entity.PrimaryPart and item:IsA("Model"), "Invalid MNPC presentation equipment")
        table.insert(owned, item)
    end

    function lease:Release()
        if released then return false end
        released = true
        -- Retire interaction before destroying the anchors. The caller has
        -- already released animation/action callbacks and mathematical OBB.
        entity:SetAttribute("Damageable", false)
        entity:SetAttribute("Game1MnpcRigReady", false)
        collider.CanQuery = false
        weld:Destroy()
        -- Equipment first, then the rig and any published wrapper siblings.
        for index = #owned, 1, -1 do
            local item = owned[index]
            if item.Parent then item:Destroy() end
        end
        table.clear(owned)
        -- Unsupported geometry uses the old FULL-only collider; it cannot be
        -- reused with an absent plan. Remove only this generation's collider.
        if fallbackRootWeld then
            fallbackRootWeld:Destroy()
            collider:Destroy()
        end
        return true
    end

    return table.freeze(lease)
end

return table.freeze(Lifecycle)
