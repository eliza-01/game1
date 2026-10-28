--!strict
-- Server-authoritative rigid door movement. The hinge is the Model pivot;
-- never animate skin Bones or modify an imported FBX pose.
local TweenService = game:GetService("TweenService")

local Doors = {}
local active: {[Model]: {tween: Tween?, value: CFrameValue?, connection: RBXScriptConnection?}} = {}
local ANGLE = math.rad(90)
local DURATION = 0.42

local function clearAnimation(door: Model)
    local entry = active[door]
    if not entry then return end
    active[door] = nil
    if entry.tween then entry.tween:Cancel() end
    if entry.connection then entry.connection:Disconnect() end
    if entry.value then entry.value:Destroy() end
end

function Doors.Toggle(house: Model): (boolean, string)
    local door = house:FindFirstChild("DoorAssembly")
    if not door or not door:IsA("Model") or door:GetAttribute("Game1DoorPivotMode") ~= "rigid_model" then
        return false, "DoorAssembly with authored hinge is unavailable"
    end
    -- Move an anchored rigid assembly rather than fighting physics on an
    -- otherwise decorative MeshPart while a tween is in progress.
    for _, descendant in door:GetDescendants() do
        if descendant:IsA("BasePart") then descendant.Anchored = true end
    end
    -- A second player cannot reverse a door mid-animation: predictable,
    -- single-writer transition even in a crowded multiplayer house.
    if active[door] then return false, "door is already moving" end
    local open = door:GetAttribute("Game1DoorOpen") == true
    -- Keep a stable closed pivot even during repeated actions. The original
    -- pivot is captured once for each placed instance; rotations accumulate
    -- from this reference, not from successive live transforms.
    local closed = door:GetAttribute("Game1DoorClosedWorldPivot")
    if typeof(closed) ~= "CFrame" then
        closed = door:GetPivot()
        door:SetAttribute("Game1DoorClosedWorldPivot", closed)
    end
    local target = if open then closed else closed * CFrame.Angles(0, ANGLE, 0)
    clearAnimation(door)
    local value = Instance.new("CFrameValue")
    value.Value = door:GetPivot()
    local connection = value.Changed:Connect(function(frame)
        if door.Parent then door:PivotTo(frame) end
    end)
    local tween = TweenService:Create(value, TweenInfo.new(DURATION, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {Value = target})
    active[door] = {tween = tween, value = value, connection = connection}
    door:SetAttribute("Game1DoorOpen", not open)
    tween.Completed:Connect(function()
        if active[door] and active[door].tween == tween then
            clearAnimation(door)
        end
    end)
    tween:Play()
    return true, if open then "Закрыть дверь" else "Открыть дверь"
end

function Doors.Cleanup(house: Model)
    for door in active do
        if door == house or door:IsDescendantOf(house) then clearAnimation(door) end
    end
end

return table.freeze(Doors)
