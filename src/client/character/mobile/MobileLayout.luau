-- Pure geometry: all coordinates are relative to CoreUISafeInsets, in pixels.
-- Both the combat HUD and context prompt use this same layout contract.
local Layout = {}

function Layout.Resolve(width, height)
    -- One scale for the whole cluster: preserve the reference proportions.
    -- The width cap keeps the floating stick and action cluster independent.
    local short = math.max(1, math.min(width, height))
    local attack = math.max(1, math.floor(math.min(short * .25, width / 3.65, 120)))
    local secondary = math.max(1, math.floor(attack * .46))
    local skill = secondary
    local stick = math.max(1, math.floor(attack * 1.06))
    local margin = math.floor(attack * .12)
    local gap = math.max(1, math.floor(attack * .12))
    local attackRight = math.floor(attack * .22)
    local bottom = math.floor(attack * .07)
    local weapon = math.max(1, math.floor(attack * .37))
    local weaponMargin = 2 -- device-safe top/right edge; independent of scale
    local weaponGap = math.max(1, math.floor(attack * .06))
    local attackBox = {size = attack, x = attackRight, y = bottom}
    local jumpBox = {size = secondary, x = attackRight + attack + gap, y = bottom}
    local aimBox = {size = secondary, x = jumpBox.x + secondary + gap, y = bottom}
    -- Right/bottom-relative polar coordinates, starting on the inner left.
    -- The arc is centred on Attack, not on the screen or on a separate row.
    local cx, cy = attackRight + attack/2, bottom + attack/2
    local arcRadius = attack * .98
    local skills = {}
    local maxTop = attackBox.y + attack
    local maxLeft = aimBox.x + secondary
    for i, degrees in ipairs({15, 50, 85, 117}) do
        local angle = math.rad(degrees)
        local x = math.floor(cx + arcRadius * math.cos(angle) - skill/2 + .5)
        local y = math.floor(cy + arcRadius * math.sin(angle) - skill/2 + .5)
        skills[i] = {size = skill, x = x, y = y}
        maxTop = math.max(maxTop, y + skill)
        maxLeft = math.max(maxLeft, x + skill)
    end
    return {
        stick = stick,
        radius = stick * 0.58,
        margin = margin,
        gap = gap,
        attack = attackBox,
        jump = jumpBox,
        aim = aimBox,
        skills = skills,
        weapon = {size = weapon, gap = weaponGap, margin = weaponMargin,
            height = weaponMargin + 2*weapon + weaponGap},
        clusterWidth = maxLeft - margin,
        contextBottom = maxTop + gap,
        contextWidth = math.floor(math.clamp(width * 0.36, 152, 230)),
    }
end

-- Keep the context dock independent of the combat hit targets even on very
-- short landscape views. In compact mode it sits to the left of the cluster.
function Layout.Context(width, height, panelHeight, preferredWidth)
    local bounds = Layout.Resolve(width, height)
    local right = bounds.margin
    local bottom = bounds.contextBottom
    local desiredWidth = math.min(preferredWidth or bounds.contextWidth, width - 2*bounds.margin)
    local panelWidth = desiredWidth
    if bottom + panelHeight > height - bounds.weapon.height then
        right = bounds.margin + bounds.clusterWidth + bounds.gap
        bottom = bounds.margin
        panelWidth = math.min(panelWidth, math.max(0, width - right - bounds.stick - 2*bounds.margin))
        -- Place it above the stick if a particularly narrow viewport has no
        -- horizontal space. Normal phone/tablet safe sizes never need this.
        if panelWidth < math.min(128, desiredWidth) then
            right = bounds.margin
            bottom = bounds.contextBottom
            panelWidth = desiredWidth
        end
    end
    return {width = panelWidth, x = right, y = bottom}
end

-- Wide lower-left activation area, but leave the top and centre for free look.
function Layout.IsMoveZone(x, y, width, height)
    return x >= 0 and y >= height * 0.52 and x <= width * 0.43 and y <= height
end

return table.freeze(Layout)
