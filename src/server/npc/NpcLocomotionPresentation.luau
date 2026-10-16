-- NPC movement tracks only. AI owns intent and velocity, this module owns clips.
-- Fallback is symmetrical: an unpublished Walk/Run may use the other clip.
local Tracks = require(script.Parent:WaitForChild("NpcAnimationTracks"))

local NpcLocomotionPresentation = {}
NpcLocomotionPresentation.__index = NpcLocomotionPresentation

function NpcLocomotionPresentation.new(entity: Model, animator: Animator, profile: any?, weaponSet: string)
    local walkRow = Tracks.PublishedRows(profile, "walk", weaponSet)[1]
    local runRow = Tracks.PublishedRows(profile, "run", weaponSet)[1]
    local walk = Tracks.Load(animator, walkRow or runRow, true)
    local run = if not runRow or (walk and walk.row.animationId == runRow.animationId)
        then walk else Tracks.Load(animator, runRow, true)
    if not walk then walk = run end
    if not run then run = walk end
    return setmetatable({
        entity = entity,
        walk = walk, run = run, current = nil,
        walkChannel = if walkRow then "walk" else "run",
        runChannel = if runRow then "run" else "walk",
    }, NpcLocomotionPresentation)
end

function NpcLocomotionPresentation:Play(mode: string)
    local walking = mode == "Walk"
    local clip = if walking then self.walk else self.run
    local channel = if walking then self.walkChannel else self.runChannel
    local previous = self.current
    if clip then
        -- Play destination before fading previous track to avoid rest-pose seams.
        Tracks.Play(self.entity, clip, channel)
    end
    if previous and previous ~= clip then Tracks.Stop(previous) end
    self.current = clip
    self.entity:SetAttribute("NpcAnimationState", channel)
    self.entity:SetAttribute("NpcLocomotionIntent", if walking then "Walk" else "Run")
end

function NpcLocomotionPresentation:Stop()
    Tracks.Stop(self.current)
    self.current = nil
    self.entity:SetAttribute("NpcLocomotionIntent", "")
end

function NpcLocomotionPresentation:Destroy()
    self:Stop()
    -- A fallback may reuse the same clip; Stop is idempotent.
    Tracks.Stop(self.walk)
    if self.run ~= self.walk then Tracks.Stop(self.run) end
end

return table.freeze(NpcLocomotionPresentation)
