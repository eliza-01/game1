-- Edit-mode surface placement. Does not change the imported rig's orientation,
-- bones, bind matrices, or asset identities. One click creates one stand clone.
local Placement = {}

local FOLDER_NAME = "Game1CharacterTestStands"

local function standFolder(workspace: Workspace): Folder
    local existing = workspace:FindFirstChild(FOLDER_NAME)
    if existing then
        assert(existing:IsA("Folder"), FOLDER_NAME .. " must be a Folder")
        return existing
    end
    local folder = Instance.new("Folder")
    folder.Name = FOLDER_NAME
    folder.Parent = workspace
    return folder
end

local function nextName(folder: Folder, profileId: string): string
    local stem = tostring(profileId):gsub("[^%w_%-]", "_")
    for number = 1, 9999 do
        local name = string.format("%s_%02d", stem, number)
        if not folder:FindFirstChild(name) then return name end
    end
    error("character test stand name limit reached")
end

function Placement.Place(draft: Model, surfacePoint: Vector3, workspace: Workspace): Model
    local folder = standFolder(workspace)
    local clone = draft:Clone()
    clone.Name = nextName(folder, tostring(draft:GetAttribute("Game1AnimationProfileId") or "character"))
    local ok, result = pcall(function()
        -- Freeze the test mannequin; animation changes bones, not world physics.
        -- Explicitly disable touching to keep combat and other services isolated.
        for _, object in clone:GetDescendants() do
            if object:IsA("BasePart") then
                object.Anchored = true
                object.CanCollide = false
                object.CanTouch = false
                object.CanQuery = false
            end
        end
        local bounds, size = clone:GetBoundingBox()
        local lowest = bounds.Position.Y - size.Y / 2
        local current = clone:GetPivot()
        local delta = Vector3.new(
            surfacePoint.X - current.Position.X,
            surfacePoint.Y - lowest,
            surfacePoint.Z - current.Position.Z
        )
        clone:PivotTo(CFrame.new(delta) * current)

        local box, dimensions = clone:GetBoundingBox()
        local anchor = Instance.new("Part")
        anchor.Name = "TestStandInteractionAnchor"
        anchor.Size = Vector3.new(0.2, 0.2, 0.2)
        anchor.CFrame = CFrame.new(box.Position.X, box.Position.Y, box.Position.Z)
        anchor.Anchored = true
        anchor.CanCollide = false
        anchor.CanTouch = false
        anchor.CanQuery = false
        anchor.Transparency = 1
        anchor.Parent = clone

        local prompt = Instance.new("ProximityPrompt")
        prompt.Name = "Game1NextAnimation"
        prompt:SetAttribute("Game1CharacterTestStandPrompt", true)
        prompt.KeyboardKeyCode = Enum.KeyCode.E
        prompt.HoldDuration = 0
        prompt.MaxActivationDistance = math.max(8, math.min(14, dimensions.Y * 0.35))
        prompt.RequiresLineOfSight = false
        prompt.ActionText = "Следующая анимация"
        prompt.ObjectText = tostring(clone:GetAttribute("Game1AnimationProfileId") or clone.Name)
        prompt.Parent = anchor
        clone.Parent = folder
        return clone
    end)
    if not ok then clone:Destroy(); error(result, 2) end
    return result
end

return table.freeze(Placement)
