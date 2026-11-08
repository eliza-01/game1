-- M243: one placement-ownership rule for Location Find and scoped Sync.
-- Grouping models may carry old Deco attributes; the nearest fully stamped
-- ancestor of a MeshPart is its placement. Do not infer ownership from names.
local Owner = {}
local SLUG = "Game1DecoAssetSlug"
local INSTANCE = "Game1DecoInstanceId"

local function ownsSlug(value: any, slug: string, aliases: {string}?): boolean
    if value == slug then return true end
    for _, alias in ipairs(aliases or {}) do
        if value == alias then return true end
    end
    return false
end

function Owner.ForPart(workspace: Workspace, part: MeshPart, slug: string,
    aliases: {string}?): Model?
    if not part:IsDescendantOf(workspace) then return nil end
    local authoring = workspace:FindFirstChild("Game1Authoring")
    local camera = workspace.CurrentCamera
    if (authoring and part:IsDescendantOf(authoring))
        or (camera and part:IsDescendantOf(camera)) then return nil end
    local cursor: Instance? = part.Parent
    while cursor and cursor ~= workspace do
        if cursor:IsA("Model") and (cursor:GetAttribute(SLUG) ~= nil
            or cursor:GetAttribute(INSTANCE) ~= nil) then
            -- Stop at the first claimed Model even if it belongs to another
            -- slug or lacks a valid ID. Never borrow an outer group's owner.
            if ownsSlug(cursor:GetAttribute(SLUG), slug, aliases)
                and tostring(cursor:GetAttribute(INSTANCE) or "") ~= "" then
                return cursor
            end
            return nil
        end
        cursor = cursor.Parent
    end
    return nil
end

function Owner.HasNestedPlacements(root: Model): boolean
    for _, descendant in ipairs(root:GetDescendants()) do
        if descendant:IsA("Model") and (descendant:GetAttribute(SLUG) ~= nil
            or descendant:GetAttribute(INSTANCE) ~= nil) then
            return true
        end
    end
    return false
end

return table.freeze(Owner)
