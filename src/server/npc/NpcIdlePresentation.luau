-- One responsibility: peaceful NPC idle presentation and weighted special cycles.
-- Population, combat AI, death and asset publication are not owned here.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local WeightedAnimationChoice = require(Shared:WaitForChild("animation"):WaitForChild("WeightedAnimationChoice"))
local Config = require(Shared:WaitForChild("npc"):WaitForChild("NpcAnimationConfig"))
local Tracks = require(script.Parent:WaitForChild("NpcAnimationTracks"))

local NpcIdlePresentation = {}
NpcIdlePresentation.__index = NpcIdlePresentation
local selectionRandom = Random.new()

local function roleOf(row: any): string
    local role = tostring(row.role or "")
    if role == "special" or role == "base" then
        return role
    end
    if tostring(row.sourceSlot or "") == "idle_special" or (tonumber(row.variant) or 0) > 0 then
        return "special"
    end
    return "base"
end

function NpcIdlePresentation.new(entity: Model, animator: Animator, profile: any?, weaponSet: string?, weaponPresentation: any): any
    local self = setmetatable({
        entity = entity,
        weaponPresentation = weaponPresentation,
        releaseWeaponHide = nil,
        base = nil,
        choices = {},
        activeSpecial = nil,
        active = false,
        elapsedWithoutBase = 0,
        specialStarted = 0,
        connections = {},
    }, NpcIdlePresentation)

    for _, row in ipairs(Tracks.PublishedRows(profile, "idle", weaponSet)) do
        local role = roleOf(row)
        local clip = Tracks.Load(animator, row, role == "base")
        if clip then
            clip.role = role
            if role == "base" and not self.base then
                self.base = clip
            end
            table.insert(self.choices, clip)
            if role == "special" and not clip.seam then
                -- Stopped is a fallback if a track completes before our frame-step.
                -- Ended fires AFTER the fade-out and is too late to prevent rest pose.
                table.insert(self.connections, clip.track.Stopped:Connect(function()
                    if self.active and self.activeSpecial == clip then
                        self:_finishSpecial()
                    end
                end))
            end
        end
    end
    if self.base and not self.base.seam then
        table.insert(self.connections, self.base.track.DidLoop:Connect(function()
            if self.active and not self.activeSpecial then
                self:_rollAtIdleBoundary()
            end
        end))
    end
    return self
end

function NpcIdlePresentation:_playBase(fade: number?)
    if not self.active then
        return
    end
    self.entity:SetAttribute("NpcAnimationState", "idle")
    self.entity:SetAttribute("NpcIdleVariant", "base")
    self.elapsedWithoutBase = 0
    if self.base then
        Tracks.Play(self.entity, self.base, "idle", fade or Config.TransitionSeconds)
    end
end

function NpcIdlePresentation:_releaseWeaponHide()
    local release = self.releaseWeaponHide
    self.releaseWeaponHide = nil
    if release then
        release()
    end
end

function NpcIdlePresentation:_finishSpecial()
    if not self.activeSpecial then
        return
    end
    local finished = self.activeSpecial
    self.activeSpecial = nil
    self:_releaseWeaponHide()
    if self.base and (tonumber(self.base.row.weight) or 100) > 0 then
        -- Start the destination pose BEFORE fading out the source.
        -- Keep at least one weighted animation through the transition.
        local fade = Config.SpecialExitBlendSeconds
        self:_playBase(fade)
        Tracks.Stop(finished, fade)
    else
        Tracks.Stop(finished, Config.SpecialExitBlendSeconds)
        self.entity:SetAttribute("NpcAnimationState", "idle")
        self.entity:SetAttribute("NpcIdleVariant", nil)
        self.elapsedWithoutBase = 0
    end
end

function NpcIdlePresentation:_rollAtIdleBoundary()
    if not self.active or self.activeSpecial then
        return
    end
    local selected = WeightedAnimationChoice.Select(self.choices, selectionRandom)
    if not selected or selected.role == "base" then
        -- Native idle keeps looping, but recover if the asset stopped unexpectedly.
        if self.base and selected and not self.base.track.IsPlaying then
            self:_playBase()
        end
        return
    end
    self.activeSpecial = selected
    self.specialStarted = os.clock()
    Tracks.Stop(self.base, 0.08)
    self.entity:SetAttribute("NpcAnimationState", "idle")
    self.entity:SetAttribute("NpcIdleVariant", ("special_%02d"):format(math.max(1, math.floor(tonumber(selected.row.variant) or 1))))
    if Tracks.Play(self.entity, selected, "idle", 0.08) then
        -- Animation chooses a scoped presentation override; it never owns the weapon.
        if selected.row.disarm == true then
            self.releaseWeaponHide = self.weaponPresentation:AcquireHidden()
        end
    else
        self:_finishSpecial()
    end
end

function NpcIdlePresentation:Start()
    if self.active then
        return
    end
    self.active = true
    self.entity:SetAttribute("NpcAnimationState", "idle")
    self.entity:SetAttribute("NpcIdleVariant", nil)
    if self.base and (tonumber(self.base.row.weight) or 100) > 0 then
        self:_playBase()
    else
        -- Special-only profiles work without an idle clip. A disabled base
        -- (weight 0) is never played just to make selection possible.
        self:_rollAtIdleBoundary()
    end
end

function NpcIdlePresentation:Stop()
    self.active = false
    self:_releaseWeaponHide()
    self.activeSpecial = nil
    self.elapsedWithoutBase = 0
    Tracks.Stop(self.base)
    for _, clip in ipairs(self.choices) do
        if clip.role == "special" then
            Tracks.Stop(clip)
        end
    end
    self.entity:SetAttribute("NpcIdleVariant", nil)
end

function NpcIdlePresentation:Step(delta: number)
    if not self.active then
        return
    end
    local special = self.activeSpecial
    if special then
        -- Crossfade before the special loses its final pose. Never let the
        -- animator briefly resolve an empty/rest pose at the transition.
        local remaining = Tracks.SecondsRemaining(special)
        if remaining and remaining <= Config.SpecialExitBlendSeconds then
            self:_finishSpecial()
            return
        end
        local completed = Tracks.Step(special, delta)
        if completed then
            self:_finishSpecial()
        elseif special.track.Length <= 0 and os.clock() - self.specialStarted >= Config.UnresolvedSpecialTimeoutSeconds then
            warn("[game1][npc] special idle asset did not resolve: " .. tostring(special.row.animationId))
            self:_finishSpecial()
        end
        return
    end
    if self.base and self.base.track.IsPlaying and self.base.track.Length > 0 then
        local _, wrapped = Tracks.Step(self.base, delta)
        if wrapped then
            self:_rollAtIdleBoundary()
        end
        return
    end
    -- No usable base loop: attempt weighted selection at a bounded interval.
    -- This also handles Roblox animation assets whose Length never resolves.
    self.elapsedWithoutBase += math.max(0, delta)
    if self.elapsedWithoutBase >= Config.MissingBaseIdleCycleSeconds then
        self.elapsedWithoutBase = 0
        self:_rollAtIdleBoundary()
    end
end

function NpcIdlePresentation:Destroy()
    self:Stop()
    for _, connection in ipairs(self.connections) do
        connection:Disconnect()
    end
    table.clear(self.connections)
end

return table.freeze(NpcIdlePresentation)
