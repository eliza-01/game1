-- Explicit ownership for published-mesh matches that do NOT belong to DecoManager.
-- Read-only. This module never changes an Instance, tag, ID or attachment.
-- A historical shared Mesh ID is not proof that an asset is a Deco placement.
local ExternalOwners = {}

function ExternalOwners.ForPart(part: MeshPart, workspaceService: Workspace): any?
    local cursor: Instance? = part.Parent
    while cursor and cursor ~= workspaceService do
        if cursor:IsA("Model") then
            if cursor:GetAttribute("LandscapeAuthoringTool") == "Game1LandscapePainter" then
                return {kind="landscape_attachment", model=cursor,
                    authorSlug=tostring(cursor:GetAttribute("LandscapeAssetSlug") or ""),
                    branchStrokeId=tostring(cursor:GetAttribute("LandscapeBranchStrokeId") or ""),
                    anchorKind=tostring(cursor:GetAttribute("LandscapeAnchorKind") or "")}
            end
            -- A branch's own geometry is painter-owned too, not an independent
            -- Decoration. Its attachment children are classified above first.
            if cursor:GetAttribute("AuthoringTool") == "Game1LandscapePainter" then
                return {kind="landscape_structure", model=cursor, authorSlug="",
                    branchStrokeId=tostring(cursor:GetAttribute("StrokeId") or ""),
                    anchorKind=""}
            end
            -- Roblox package models carry no Deco placement identity. Protect
            -- them, even if one of their meshes matches a Location publication.
            if cursor:FindFirstChildOfClass("PackageLink") ~= nil then
                return {kind="unmanaged_package", model=cursor, authorSlug="",
                    branchStrokeId="", anchorKind=""}
            end
            -- An explicitly stamped Location placement is a stronger boundary
            -- than a distant Package or Landscape ancestor.
            if cursor:GetAttribute("Game1DecoInstanceId") ~= nil
                or cursor:GetAttribute("Game1DecoAssetSlug") ~= nil then
                return nil
            end
        end
        cursor = cursor.Parent
    end
    return nil
end

return table.freeze(ExternalOwners)
