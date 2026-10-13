-- Actor-scoped, server-authoritative weapon presentation overrides.
-- Equipment remains attached to its sockets; temporary hiding never unequips it.
-- Scopes are reference-counted so later actions may coexist without stale callbacks
-- accidentally restoring a still-suppressed weapon.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Contract = require(ReplicatedStorage:WaitForChild("Game1Shared")
    :WaitForChild("weapon"):WaitForChild("WeaponPresentationContract"))

local WeaponPresentationState = {}
WeaponPresentationState.__index = WeaponPresentationState

function WeaponPresentationState.new(actor: Model)
    local self = setmetatable({
        actor = actor,
        nextToken = 0,
        tokens = {},
        hiddenCount = 0,
        destroyed = false,
    }, WeaponPresentationState)
    actor:SetAttribute(Contract.HiddenAttribute, false)
    return self
end

function WeaponPresentationState:AcquireHidden(): () -> ()
    if self.destroyed then
        return function() end
    end
    self.nextToken += 1
    local token = self.nextToken
    self.tokens[token] = true
    self.hiddenCount += 1
    if self.hiddenCount == 1 then
        self.actor:SetAttribute(Contract.HiddenAttribute, true)
    end

    local released = false
    return function()
        if released then
            return
        end
        released = true
        if self.destroyed or not self.tokens[token] then
            return
        end
        self.tokens[token] = nil
        self.hiddenCount -= 1
        if self.hiddenCount == 0 then
            self.actor:SetAttribute(Contract.HiddenAttribute, false)
        end
    end
end

function WeaponPresentationState:Destroy()
    if self.destroyed then
        return
    end
    self.destroyed = true
    table.clear(self.tokens)
    self.hiddenCount = 0
    if self.actor.Parent then
        self.actor:SetAttribute(Contract.HiddenAttribute, false)
    end
end

return table.freeze(WeaponPresentationState)
