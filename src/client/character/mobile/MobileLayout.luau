-- Pure geometry: all coordinates are relative to CoreUISafeInsets, in pixels.
-- Both the combat HUD and context prompt use this same layout contract.
local Layout = {}

function Layout.Resolve(width, height)
    local short = math.min(width, height)
    local secondary = math.floor(math.clamp(short * 0.16, 48, 66))
    local attack = math.floor(math.clamp(short * 0.22, 64, 90))
    local margin = math.floor(math.clamp(short * 0.055, 12, 24))
    local gap = math.floor(math.clamp(short * 0.035, 8, 14))
    local stick = math.floor(math.clamp(short * 0.25, 76, 112))
    return {
        stick = stick,
        radius = stick * 0.58,
        margin = margin,
        jump = {size = secondary, x = margin, y = margin},
        attack = {size = attack, x = margin + secondary + gap, y = margin + gap},
        aim = {size = secondary, x = margin, y = margin + secondary + gap},
        contextBottom = margin + math.max(secondary * 2 + gap, attack + gap) + gap,
        contextWidth = math.floor(math.clamp(width * 0.36, 152, 230)),
    }
end

-- Keep the context dock independent of the combat hit targets even on very
-- short landscape views. In compact mode it sits to the left of the cluster.
function Layout.Context(width, height, panelHeight)
    local bounds = Layout.Resolve(width, height)
    local right = bounds.margin
    local bottom = bounds.contextBottom
    local panelWidth = bounds.contextWidth
    if bottom + panelHeight > height then
        right = bounds.attack.x + bounds.attack.size + bounds.margin
        bottom = bounds.margin
        panelWidth = math.min(panelWidth, math.max(0, width - right - bounds.stick - 2*bounds.margin))
        -- Place it above the stick if a particularly narrow viewport has no
        -- horizontal space. Normal phone/tablet safe sizes never need this.
        if panelWidth < 128 then
            right = bounds.margin
            bottom = math.max(0, height - panelHeight)
            panelWidth = bounds.contextWidth
        end
    end
    return {width = panelWidth, x = right, y = bottom}
end

-- Wide lower-left activation area, but leave the top and centre for free look.
function Layout.IsMoveZone(x, y, width, height)
    return x >= 0 and y >= height * 0.52 and x <= width * 0.43 and y <= height
end

return table.freeze(Layout)
