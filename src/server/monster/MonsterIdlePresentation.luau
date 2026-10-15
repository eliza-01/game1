-- M92: monster idle / combat-idle presentation and native track callbacks.
-- No spawn, locomotion, death, or population ownership. Connections are
-- registered through the caller's M91 instance-scoped watch registry.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local AnimationSpeedScaling = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("animation"):WaitForChild("AnimationSpeedScaling"))

local MonsterIdlePresentation = {}

local function finite(value: any, fallback: number): number
    local number = tonumber(value)
    if number == nil or number ~= number or number == math.huge or number == -math.huge then
        return fallback
    end
    return number
end

function MonsterIdlePresentation.new(spawnRandom: Random): any
    local function playTrackAtConfiguredSpeed(model: Model, track: AnimationTrack?, channel: string, fadeTime: number)
        if not track then
            return
        end
        local percent = AnimationSpeedScaling.ResolveForAnimation(model, channel, track.Animation and track.Animation.AnimationId)
        model:SetAttribute("AnimationPlaybackSpeedPercent", percent)
        local speed = percent / 100
        if track.IsPlaying then
            track:AdjustSpeed(speed)
        else
            track:Play(fadeTime, 1, speed)
        end
    end

    local function stopTrack(track: AnimationTrack?)
        if not track then
            return
        end
        pcall(function()
            track:Stop(0.08)
        end)
    end

    local function weightedIdleChoice(choices: {any}): any?
        local total = 0
        for _, choice in ipairs(choices) do
            total += math.max(1, finite(choice.row and choice.row.weight, 100))
        end
        if total <= 0 then
            return nil
        end
        local roll = spawnRandom:NextNumber(0, total)
        local cursor = 0
        for _, choice in ipairs(choices) do
            cursor += math.max(1, finite(choice.row and choice.row.weight, 100))
            if roll <= cursor then
                return choice
            end
        end
        return choices[#choices]
    end

    local function stopIdleState(entry: any)
        stopTrack(entry.idleTrack)
        for _, choice in ipairs(entry.idleChoices or {}) do
            if choice.role == "special" then
                stopTrack(choice.track)
            end
        end
        entry.activeIdleSpecial = nil
    end

    local function playBaseIdle(model: Model, entry: any)
        if entry.dying or model:GetAttribute("MonsterCombatActive") == true or model:GetAttribute("InCombat") == true then
            return
        end
        stopTrack(entry.walkTrack)
        stopTrack(entry.runTrack)
        model:SetAttribute("MonsterAnimationState", "idle")
        model:SetAttribute("MonsterIdleVariant", "base")
        if entry.idleTrack then
            pcall(function()
                playTrackAtConfiguredSpeed(model, entry.idleTrack, "idle", 0.12)
            end)
        end
    end

    local function playCombatIdleState(model: Model, entry: any)
        if entry.dying or model:GetAttribute("MonsterCombatActive") == true then
            return
        end
        stopIdleState(entry)
        stopTrack(entry.walkTrack)
        stopTrack(entry.runTrack)
        model:SetAttribute("MonsterAnimationState", "combat_idle")
        model:SetAttribute("MonsterIdleVariant", "combat")
        if entry.combatIdleTrack then
            pcall(function()
                playTrackAtConfiguredSpeed(model, entry.combatIdleTrack, "combat_idle", 0.1)
            end)
        end
    end

    local function maybePlayIdleSpecial(model: Model, entry: any)
        if entry.dying or entry.wandering or entry.activeIdleSpecial ~= nil
            or model:GetAttribute("InCombat") == true or model:GetAttribute("MonsterCombatActive") == true then
            return
        end
        local choice = weightedIdleChoice(entry.idleChoices or {})
        if not choice or choice.role ~= "special" then
            return
        end
        entry.activeIdleSpecial = choice
        stopTrack(entry.idleTrack)
        model:SetAttribute("MonsterAnimationState", "idle")
        model:SetAttribute("MonsterIdleVariant", ("special_%02d"):format(math.max(1, math.floor(finite(choice.row.variant, 1)))))
        local ok = pcall(function()
            playTrackAtConfiguredSpeed(model, choice.track, "idle", 0.08)
        end)
        if not ok then
            entry.activeIdleSpecial = nil
            playBaseIdle(model, entry)
        end
    end

    -- Callbacks are identical to M91. Ownership belongs to the registerSignal
    -- callback (Spawner's watch(entry, ...)), not to this presentation module.
    local function bindIdleEvents(model: Model, entry: any, registerSignal: any, isCurrent: any)
        for _, choice in ipairs(entry.idleChoices) do
            if choice.role == "special" then
                registerSignal(choice.track.Ended, function()
                    if not isCurrent() or entry.dying or entry.activeIdleSpecial ~= choice then
                        return
                    end
                    entry.activeIdleSpecial = nil
                    playBaseIdle(model, entry)
                end)
            end
        end
        local idleTrack = entry.idleTrack
        if idleTrack then
            registerSignal(idleTrack.DidLoop, function()
                if isCurrent() then
                    maybePlayIdleSpecial(model, entry)
                end
            end)
        end
    end

    return table.freeze({
        stopTrack = stopTrack,
        stopIdleState = stopIdleState,
        playBaseIdle = playBaseIdle,
        playCombatIdleState = playCombatIdleState,
        playTrackAtConfiguredSpeed = playTrackAtConfiguredSpeed,
        BindIdleEvents = bindIdleEvents,
    })
end

return table.freeze(MonsterIdlePresentation)
