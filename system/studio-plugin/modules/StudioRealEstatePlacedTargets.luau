-- One authoritative definition of a placed Real Estate instance.
-- ServerStorage owns the publishing template. Any matching Model *inside*
-- Workspace is a placed copy, even when cloned with the template flag intact.
-- Run only on explicit Studio Sync commands, never per frame.
local Targets = {}

function Targets.List(slug: string): {Model}
    local matches = {}
    if slug == "" then return matches end
    for _, instance in workspace:GetDescendants() do
        if instance:IsA("Model") and instance:GetAttribute("Game1RealEstateSlug") == slug then
            -- Do not count nested models with a duplicate slug twice.
            local ancestor = instance.Parent
            local nested = false
            while ancestor and ancestor ~= workspace do
                if ancestor:IsA("Model") and ancestor:GetAttribute("Game1RealEstateSlug") == slug then
                    nested = true
                    break
                end
                ancestor = ancestor.Parent
            end
            if not nested then
                table.insert(matches, instance)
            end
        end
    end
    table.sort(matches, function(a, b) return a:GetFullName() < b:GetFullName() end)
    return matches
end

function Targets.MarkPlaced(root: Model)
    -- A template clone moved to Workspace must no longer claim to be the
    -- ServerStorage template. Do this only after a successful model swap.
    if root:GetAttribute("Game1RealEstateTemplate") == true then
        root:SetAttribute("Game1RealEstateTemplate", nil)
    end
end

return table.freeze(Targets)
