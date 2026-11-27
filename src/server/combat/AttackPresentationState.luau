-- Atomic, server-owned attack presentation snapshot. One replicated attribute
-- per accepted attack, updated on bounce and removed on completion.
local HttpService = game:GetService("HttpService")
local Workspace = game:GetService("Workspace")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Phase = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("combat"):WaitForChild("AttackPresentationPhase"))
local State = {}
State.Attribute = Phase.Attribute

function State.Begin(character: Model, serial: number, descriptor: any, duration: number): any?
    local animationId = descriptor and tostring(descriptor.animationId or "") or ""
    if not animationId:match("^rbxassetid://%d+$") then return nil end
    local now = Workspace:GetServerTimeNow()
    local state = {serial = serial, clipId = tostring(descriptor.clipId), animationId = animationId,
        startAt = now, duration = duration, endAt = now + duration}
    character:SetAttribute(State.Attribute, HttpService:JSONEncode(state))
    return state
end

function State.Bounce(character: Model, state: any?, reverseSpeed: number, recovery: number)
    if not state then return end
    local now = Workspace:GetServerTimeNow()
    state.bouncePhase = math.clamp((now - state.startAt) / state.duration, 0, 1)
    state.bounceAt = now
    state.reverseSpeed = math.max(0.1, reverseSpeed)
    state.endAt = now + recovery
    character:SetAttribute(State.Attribute, HttpService:JSONEncode(state))
end

function State.Clear(character: Model)
    character:SetAttribute(State.Attribute, nil)
end

return table.freeze(State)
