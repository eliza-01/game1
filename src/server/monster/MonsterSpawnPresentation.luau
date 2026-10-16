-- Spawn-only visual presentation. Owns fade/rise and physics landing,
-- not population or death. AI is gated until the rig has landed.
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")

local MonsterSpawnPresentation = {}
local FADE_SECONDS = 1.15
local RISE_SECONDS = 1.5
local RISE_CLEARANCE_STUDS = 1.25
-- The visible descent always takes this long, independently of clearance height.
local LANDING_SECONDS = 1.5
local SETTLE_CONFIRM_SECONDS = 0.12
local MIN_FALL_SECONDS = 0.2
local MAX_FALL_SECONDS = 4.0
local POSITION_TOLERANCE_STUDS = 0.6
local VERTICAL_SPEED_TOLERANCE = 0.2

-- Prepare before animation loading (which can yield) to prevent a visible pop.
function MonsterSpawnPresentation.Prepare(model: Model, visual: Model, navigationRoot: BasePart, humanoid: Humanoid, riseFromGround: boolean): any
    local alpha = {}
    for _, descendant in ipairs(visual:GetDescendants()) do
        if (descendant:IsA("BasePart") or descendant:IsA("Decal") or descendant:IsA("Texture"))
            and descendant.Transparency < 1 then
            table.insert(alpha, {instance = descendant, original = descendant.Transparency})
            descendant.Transparency = 1
        end
    end

    model:SetAttribute("MonsterSpawning", true)
    model:SetAttribute("Damageable", false)

    local finishCFrame = navigationRoot.CFrame
    local raisedCFrame = finishCFrame + Vector3.new(0, RISE_CLEARANCE_STUDS, 0)
    local oldAnchored = navigationRoot.Anchored
    local oldCanCollide = navigationRoot.CanCollide
    local oldCanQuery = navigationRoot.CanQuery
    if riseFromGround then
        local depth = math.max(1, visual:GetExtentsSize().Y + 0.25)
        navigationRoot.Anchored = true
        navigationRoot.CanCollide = false
        navigationRoot.CanQuery = false
        navigationRoot.CFrame = finishCFrame - Vector3.new(0, depth, 0)
    end

    local playing = false
    local cancelled = false
    local tweens = {}
    local duration = if riseFromGround then RISE_SECONDS else FADE_SECONDS
    local info = TweenInfo.new(duration, Enum.EasingStyle.Sine, Enum.EasingDirection.Out)
    local presentation = {}

    local function active(): boolean
        return not cancelled and model.Parent ~= nil and navigationRoot.Parent ~= nil
            and tostring(model:GetAttribute("LifeState") or "") == "Alive"
    end

    local function finish(onReady: () -> ())
        if not active() then
            return
        end
        cancelled = true -- Only one completion, even if Cancel() races with the fall.
        for _, item in ipairs(alpha) do
            if item.instance.Parent then
                item.instance.Transparency = item.original
            end
        end
        table.clear(tweens)
        model:SetAttribute("Damageable", true)
        model:SetAttribute("MonsterSpawning", false)
        onReady()
    end

    local function releaseToGravity(onReady: () -> ())
        -- The timed descent has reached the authored ground position. Hand
        -- over to physics only now, with the navigation body clear of terrain.
        navigationRoot.CFrame = finishCFrame
        navigationRoot.AssemblyLinearVelocity = Vector3.zero
        navigationRoot.AssemblyAngularVelocity = Vector3.zero
        navigationRoot.CanCollide = oldCanCollide
        navigationRoot.CanQuery = oldCanQuery
        navigationRoot.Anchored = oldAnchored
        if not oldAnchored then
            pcall(function() navigationRoot:SetNetworkOwner(nil) end)
            pcall(function() humanoid:ChangeState(Enum.HumanoidStateType.Freefall) end)
        end

        task.spawn(function()
            local fallingSince = os.clock()
            local settledSince: number? = nil
            while active() do
                RunService.Heartbeat:Wait()
                local elapsed = os.clock() - fallingSince
                local onFloor = humanoid.Parent ~= nil and humanoid.FloorMaterial ~= Enum.Material.Air
                -- The 1.5s descent has already reached the authored landing
                -- position. Physics is responsible only for the final contact.
                local heightAboveLanding = navigationRoot.Position.Y - finishCFrame.Position.Y
                if elapsed >= MIN_FALL_SECONDS then
                    local nearAuthoredHeight = math.abs(heightAboveLanding) <= POSITION_TOLERANCE_STUDS
                    local stoppedFalling = math.abs(navigationRoot.AssemblyLinearVelocity.Y) <= VERTICAL_SPEED_TOLERANCE
                    if nearAuthoredHeight and stoppedFalling then
                        settledSince = settledSince or os.clock()
                    else
                        settledSince = nil
                    end
                    -- Custom navigation rigs can report FloorMaterial=Air even
                    -- when physically resting. Confirm actual stabilization
                    -- after the 1.5s movement before enabling monster AI.
                    if onFloor or (settledSince ~= nil and os.clock() - settledSince >= SETTLE_CONFIRM_SECONDS) then
                        finish(onReady)
                        return
                    end
                end
                if elapsed >= MAX_FALL_SECONDS then
                    -- Do not permanently block this monster if Humanoid.FloorMaterial
                    -- stays Air on a custom rig. Studio should still validate landing.
                    warn("[game1][monster-spawn] ground-rise landing timeout: " .. model.Name)
                    finish(onReady)
                    return
                end
            end
        end)
    end

    function presentation:Start(onReady: () -> ())
        if playing or cancelled then
            return
        end
        playing = true
        for _, item in ipairs(alpha) do
            if item.instance.Parent then
                local tween = TweenService:Create(item.instance, info, {Transparency = item.original})
                table.insert(tweens, tween)
                tween:Play()
            end
        end
        if riseFromGround and navigationRoot.Parent then
            local movement = TweenService:Create(navigationRoot, info, {CFrame = raisedCFrame})
            table.insert(tweens, movement)
            movement:Play()
        end

        task.delay(duration, function()
            if not active() then
                return
            end
            if riseFromGround then
                -- Tween the actual distance to the landing point over exactly
                -- LANDING_SECONDS, not at a fixed studs/second rate. Keep the
                -- navigation root anchored and non-collidable until completion.
                local landingInfo = TweenInfo.new(LANDING_SECONDS, Enum.EasingStyle.Sine, Enum.EasingDirection.Out)
                local landingTween = TweenService:Create(navigationRoot, landingInfo, {CFrame = finishCFrame})
                table.insert(tweens, landingTween)
                landingTween:Play()
                local playbackState = landingTween.Completed:Wait()
                if playbackState ~= Enum.PlaybackState.Completed or not active() then
                    return
                end
                -- Only the short contact verification runs under physics.
                releaseToGravity(onReady)
            else
                finish(onReady)
            end
        end)
    end

    function presentation:Cancel()
        if cancelled then
            return
        end
        cancelled = true
        for _, tween in ipairs(tweens) do
            tween:Cancel()
        end
        table.clear(tweens)
        -- Preserve authored opacity if the monster dies during rise/fall.
        for _, item in ipairs(alpha) do
            if item.instance.Parent then
                item.instance.Transparency = item.original
            end
        end
        -- Do not unanchor here: death lifecycle owns the frozen corpse.
    end

    return table.freeze(presentation)
end

return table.freeze(MonsterSpawnPresentation)
