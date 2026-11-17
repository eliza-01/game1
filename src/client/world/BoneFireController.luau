-- M365 · Bone-authored Fire is rooted at the Bone head and emits toward world +Y.
-- Only presentation is changed. Authoring Fire instances/presets are not cloned,
-- published or mutated on the server. Existing untagged Fire also works.
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Controller = {}
local STEP = 1 / 30
local ANCHOR_NAME = "Game1FireDirection"

local tracked: {[Fire]: {bone: Bone, anchor: Attachment, lastRotation: CFrame?, expectedLocalFrame: CFrame?}} = {}
local count = 0
local connection: RBXScriptConnection? = nil
local started = false

local function ownerBone(fire: Fire): Bone?
    local current = fire.Parent
    while current do
        if current:IsA("Bone") then return current end
        -- Do not pull a Fire out of a separate BasePart in the rig.
        if current:IsA("BasePart") then return nil end
        if not current:IsA("Attachment") then return nil end
        current = current.Parent
    end
    return nil
end

local function forget(fire: Fire)
    if tracked[fire] then
        tracked[fire] = nil
        count -= 1
        if count == 0 and connection then
            connection:Disconnect()
            connection = nil
        end
    end
end

local function update(fire: Fire, state)
    if not fire:IsDescendantOf(Workspace) or not state.bone:IsDescendantOf(Workspace)
        or fire.Parent ~= state.anchor or state.anchor.Parent ~= state.bone then
        forget(fire)
        return
    end
    -- The Attachment is at bone-head (local zero). Cancel the animated Bone
    -- rotation, never its position: +Y of the native Fire becomes world +Y.
    local rotation = state.bone.TransformedWorldCFrame.Rotation
    if rotation ~= state.lastRotation then
        state.expectedLocalFrame = rotation:Inverse()
        state.lastRotation = rotation
    end
    if state.anchor.CFrame ~= state.expectedLocalFrame then
        state.anchor.CFrame = state.expectedLocalFrame
    end
    -- Negative Heat reverses native Fire's emission direction.
    if fire.Heat < 0 then fire.Heat = -fire.Heat end
end

-- No heartbeat at all until at least one bone-mounted Fire is present.
local accumulator = 0
local function ensureLoop()
    if connection then return end
    accumulator = 0
    connection = RunService.Heartbeat:Connect(function(dt)
        accumulator += dt
        if accumulator < STEP then return end
        accumulator %= STEP
        for fire, state in pairs(tracked) do
            update(fire, state)
        end
    end)
end

local function track(fire: Fire)
    if tracked[fire] or not fire:IsDescendantOf(Workspace) then return end
    local bone = ownerBone(fire)
    if not bone then return end
    local anchor: Attachment?
    local parent = fire.Parent
    if parent and parent.ClassName == "Attachment" and parent.Name:sub(1, #ANCHOR_NAME) == ANCHOR_NAME
        and parent.Parent == bone then
        anchor = parent :: Attachment
    else
        -- Local-only adapter for earlier authored Fire (direct Bone / custom
        -- Attachment). No persistent Place mutations, no separate fire clone.
        local candidate = bone:FindFirstChild(ANCHOR_NAME)
        if candidate and candidate:IsA("Attachment") and not candidate:FindFirstChildOfClass("Fire") then
            anchor = candidate
        else
            local name = ANCHOR_NAME
            local suffix = 2
            while bone:FindFirstChild(name) do
                name = ANCHOR_NAME .. tostring(suffix)
                suffix += 1
            end
            anchor = Instance.new("Attachment")
            anchor.Name = name
            anchor.Parent = bone
        end
    end
    local state = {bone = bone, anchor = anchor :: Attachment, lastRotation = nil, expectedLocalFrame = nil}
    tracked[fire] = state
    count += 1
    if fire.Parent ~= anchor then fire.Parent = anchor end
    update(fire, state)
    ensureLoop()
end

function Controller.Start()
    if started then return end
    started = true
    -- One discovery pass, not a per-frame Workspace scan. DescendantAdded
    -- catches streaming, new placements, and monster/character respawns.
    Workspace.DescendantAdded:Connect(function(item)
        if item:IsA("Fire") then track(item) end
    end)
    for _, item in ipairs(Workspace:GetDescendants()) do
        if item:IsA("Fire") then track(item) end
    end
end

return table.freeze(Controller)
