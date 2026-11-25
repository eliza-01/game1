--!strict
-- Both camera and preview must use the same authored pair, or neither.
local Workspace = game:GetService("Workspace")
local Scene = {}
export type Anchors = {preview: CFrame, camera: CFrame, fov: number}
local function pivot(marker: Instance?): CFrame?
    if marker and (marker:IsA("BasePart") or marker:IsA("Model")) then return marker:GetPivot() end
    return nil
end
function Scene.Resolve(): Anchors?
    local places = Workspace:FindFirstChild("Places")
    local selection = places and places:FindFirstChild("Character Selection")
    local camera = selection and selection:FindFirstChild("CharacterSelectionCamera", true)
    local preview = selection and selection:FindFirstChild("CharacterSelectionPreviewPoint", true)
    local cameraFrame, previewFrame = pivot(camera), pivot(preview)
    if not cameraFrame or not previewFrame or not camera then return nil end
    return {preview = previewFrame, camera = cameraFrame,
        fov = math.clamp(tonumber(camera:GetAttribute("FieldOfView")) or 65, 25, 100)}
end
return table.freeze(Scene)
