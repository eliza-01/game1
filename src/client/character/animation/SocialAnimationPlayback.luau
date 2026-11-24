--!strict
-- Reusable presentation-only social animation. Player and creation scene both
-- pass their existing Animator's AnimationTrackCache; never owns combat state.
local Resolver = require(script.Parent:WaitForChild("AnimationResolver"))

local Social = {}

function Social.Resolve(character: Model, slot: string): any?
    -- Resolve published social clips from the canonical registry instead of
    -- maintaining a second slot whitelist in the client.
    if slot == "" then
        return nil
    end
    local row = Resolver.Resolve(character, "social", nil, slot)
    if row and tostring(row.animationId or ""):match("^rbxassetid://[1-9]%d*$") then
        return row
    end
    return nil
end

Social.__index = Social

function Social.new(character: Model, cache: any): any
    return setmetatable({character = character, cache = cache, activeTrack = nil, destroyed = false}, Social)
end

function Social:Play(slot: string): AnimationTrack?
    if self.destroyed then return nil end
    local descriptor = Social.Resolve(self.character, slot)
    if not descriptor or not self.cache then return nil end
    local track = self.cache:Get(descriptor)
    if not track then return nil end
    self:Stop(0.12)
    track.Looped = false
    track:Play(0.12)
    self.activeTrack = track
    return track
end

function Social:Stop(fadeSeconds: number?)
    local track = self.activeTrack
    self.activeTrack = nil
    if track and track.IsPlaying then
        track:Stop(fadeSeconds or 0.12)
    end
end

function Social:Destroy()
    if self.destroyed then return end
    self.destroyed = true
    self:Stop(0)
    -- AnimationTrackCache and Animator are owned by their surrounding actor.
end

return table.freeze(Social)
