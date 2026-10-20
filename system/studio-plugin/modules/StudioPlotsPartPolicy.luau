-- Reversible, Studio-only properties for Plots visibility and playtest preview.
-- This policy never reparents, destroys, or moves authored instances.
local Policy = {}

function Policy.Capture(part: BasePart): any
    return {
        localTransparency = part.LocalTransparencyModifier,
        transparency = part.Transparency,
        color = part.Color,
        anchored = part.Anchored,
        locked = part.Locked,
        canCollide = part.CanCollide,
        canQuery = part.CanQuery,
        canTouch = part.CanTouch,
        castShadow = part.CastShadow,
    }
end

local function applyInteraction(part: BasePart, saved: any, accessible: boolean, playtest: boolean)
    -- CanQuery=false requires CanCollide=false. Set collision first.
    part.CanCollide = false
    if accessible then
        part.CanQuery = saved.canQuery
        part.CanTouch = saved.canTouch
        part.Locked = saved.locked
        -- In Play these are previews, never solid walls around plots.
        if not playtest then
            part.CanCollide = saved.canCollide
        end
    else
        part.CanQuery = false
        part.CanTouch = false
        part.Locked = true
    end
end

function Policy.Edit(part: BasePart, saved: any, _accessible: boolean)
    -- Viewport selection is independent of Locked/CanQuery. The filter module
    -- handles StudioSelectable while preserving the original interaction state.
    applyInteraction(part, saved, true, false)
    -- Transparency is driven by the preview controller's tweens in Edit mode.
end

function Policy.Play(part: BasePart, saved: any, visible: boolean, isVolume: boolean, tint: Color3, alpha: number)
    applyInteraction(part, saved, visible, true)
    if visible then
        if isVolume then
            part.Anchored = true
            part.Color = tint
            part.Transparency = alpha
            part.CastShadow = false
            part.LocalTransparencyModifier = 0
        else
            part.Transparency = saved.transparency
            part.LocalTransparencyModifier = saved.localTransparency
        end
    else
        -- Hidden parts are visually and physically absent from simulation.
        -- Keeping hierarchy intact avoids destructive edits to authored plots.
        part.Transparency = 1
        part.LocalTransparencyModifier = 1
        part.CastShadow = false
        if isVolume then
            part.Anchored = true
        end
    end
end

function Policy.Restore(part: BasePart, saved: any)
    if not part.Parent then return end
    part.LocalTransparencyModifier = saved.localTransparency
    part.Transparency = saved.transparency
    part.Color = saved.color
    part.Anchored = saved.anchored
    part.CastShadow = saved.castShadow
    applyInteraction(part, saved, true, false)
end

return table.freeze(Policy)
