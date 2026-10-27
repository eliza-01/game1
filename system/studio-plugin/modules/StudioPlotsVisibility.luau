-- Studio-only Plots preview: hidden -> volumes -> volumes + numbers -> hidden.
-- Edit previews live in CoreGui; Play uses reversible physical appearance.
-- Never change CFrame, Size, constraints or hierarchy.
local StudioPlotsCatalog = require(script.Parent.StudioPlotsCatalog)
local StudioPlotsPartPolicy = require(script.Parent.StudioPlotsPartPolicy)
local StudioPlotsSelectionFilter = require(script.Parent.StudioPlotsSelectionFilter)

local PlotsVisibility = {}
PlotsVisibility.__index = PlotsVisibility

local FADE = TweenInfo.new(0.4, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
local VOLUME_ALPHA = 0.78
local VOLUME_COLOR = Color3.fromRGB(61, 195, 213)

function PlotsVisibility.new(config: any)
    local self = setmetatable({
        workspace = config.Workspace,
        coreGui = config.CoreGui,
        tweenService = config.TweenService,
        runService = config.RunService,
        state = 0,
        destroyed = false,
        tweens = {},
        overlays = {},
        sizeConnections = {},
        originalProperties = {},
        phase = if config.RunService.RunState == Enum.RunState.Stopped then "edit" else "play",
        selection = config.Selection,
        selectionFilter = StudioPlotsSelectionFilter.new(config.PhysicsService),
        volumeParts = {},
        numberParts = {},
        connections = {},
    }, PlotsVisibility)

    self.button = config.toolbar:CreateButton(
        "Game1Plots", "Plots: volumes → numbers → hidden", "", "Plots"
    )
    self.button.ClickableWhenViewportHidden = true
    self.button:SetActive(false)

    table.insert(self.connections, self.button.Click:Connect(function()
        self:Next()
    end))
    table.insert(self.connections, config.plugin.Unloading:Connect(function()
        self:Destroy()
    end))
    table.insert(self.connections, config.RunService:GetPropertyChangedSignal("RunState"):Connect(function()
        if self.destroyed then return end
        local runState = self.runService.RunState
        -- Paused Play/Run is still the same simulation; do not reset it.
        if runState == Enum.RunState.Paused then return end
        local phase = if runState == Enum.RunState.Stopped then "edit" else "play"
        if phase == self.phase then return end
        self:_release()
        self.phase = phase
        -- The runtime Workspace can be swapped when Play begins. Discover
        -- plots after that transition, not from the old edit-mode collection.
        task.defer(function()
            if self.destroyed or self.phase ~= phase then return end
            self:_refresh()
        end)
    end))

    self:_refresh()
    print("[game1][plots] toolbar ready · button=Game1Plots · initial=hidden")
    return self
end

function PlotsVisibility:_cancel(instance: Instance)
    local tween = self.tweens[instance]
    if tween then
        self.tweens[instance] = nil
        tween:Cancel()
    end
end

function PlotsVisibility:_fade(instance: Instance, property: string, target: number)
    self:_cancel(instance)
    if (instance :: any)[property] == target then return end
    local tween = self.tweenService:Create(instance, FADE, { [property] = target })
    self.tweens[instance] = tween
    tween.Completed:Connect(function()
        if self.tweens[instance] == tween then self.tweens[instance] = nil end
    end)
    tween:Play()
end

function PlotsVisibility:_snapshot(part: BasePart)
    if not self.originalProperties[part] then
        local saved = StudioPlotsPartPolicy.Capture(part)
        saved.collisionGroup = StudioPlotsSelectionFilter.OriginalGroup(part)
        self.originalProperties[part] = saved
    end
    return self.originalProperties[part]
end

function PlotsVisibility:_restore(part: BasePart)
    self:_cancel(part)
    local original = self.originalProperties[part]
    if original then
        self.selectionFilter:Restore(part, original.collisionGroup)
        StudioPlotsPartPolicy.Restore(part, original)
    end
    self.originalProperties[part] = nil
end

function PlotsVisibility:_removeHiddenSelection()
    if self.phase ~= "edit" or not self.selection then return end
    local kept = {}
    local changed = false
    for _, item in ipairs(self.selection:Get()) do
        local hidden = false
        for volume, _ in pairs(self.volumeParts) do
            if item == volume and self.state == 0 then
                hidden = true
                break
            end
        end
        if not hidden then
            for part, _ in pairs(self.numberParts) do
                -- Never deselect a volume or plot folder merely because it
                -- contains a hidden numbered model.
                local isVolumeOrFolder = self.volumeParts[item] == true
                if not isVolumeOrFolder then
                    for volume, _ in pairs(self.volumeParts) do
                        if item:IsAncestorOf(volume) then
                            isVolumeOrFolder = true
                            break
                        end
                    end
                end
                if (item == part or (item:IsAncestorOf(part) and not isVolumeOrFolder))
                    and self.state ~= 2 then
                    hidden = true
                    break
                end
            end
        end
        if hidden then changed = true else table.insert(kept, item) end
    end
    if changed then self.selection:Set(kept) end
end

function PlotsVisibility:_overlay(volume: BasePart)
    local adornment = self.overlays[volume]
    if adornment then return adornment end

    -- CoreGui is not serialized into the place. Adornee follows the volume's
    -- CFrame automatically; Size is mirrored for resizing in Edit mode.
    adornment = Instance.new("BoxHandleAdornment")
    adornment.Name = "Game1PlotsPreview"
    adornment.Adornee = volume
    adornment.Size = volume.Size
    adornment.Color3 = VOLUME_COLOR
    adornment.Transparency = 1
    adornment.AlwaysOnTop = false
    adornment.Parent = self.coreGui
    self.overlays[volume] = adornment
    self.sizeConnections[volume] = volume:GetPropertyChangedSignal("Size"):Connect(function()
        adornment.Size = volume.Size
    end)
    return adornment
end

function PlotsVisibility:_refresh()
    if self.destroyed then return 0, 0, 0 end
    local entries, missingVolumes, missingNumbers = StudioPlotsCatalog.Collect(self.workspace)
    local currentVolumes = {}
    local currentNumbers = {}
    local playtest = self.phase == "play"
    for _, entry in ipairs(entries) do
        local volume = entry.volume
        currentVolumes[volume] = true
        local volumeOriginal = self:_snapshot(volume)
        if playtest then
            self.selectionFilter:Restore(volume, volumeOriginal.collisionGroup)
            StudioPlotsPartPolicy.Play(volume, volumeOriginal,
                self.state ~= 0, true, VOLUME_COLOR, VOLUME_ALPHA)
        else
            -- StudioSelectable filtering makes the invisible volume truly
            -- click-through in the editor, without touching scene geometry.
            StudioPlotsPartPolicy.Edit(volume, volumeOriginal, self.state ~= 0)
            if self.state == 0 then
                self.selectionFilter:Hide(volume, volumeOriginal.collisionGroup)
            else
                self.selectionFilter:Restore(volume, volumeOriginal.collisionGroup)
            end
            volume.LocalTransparencyModifier = 1
            local overlay = self:_overlay(volume)
            self:_fade(overlay, "Transparency", if self.state == 0 then 1 else VOLUME_ALPHA)
        end
        for _, numberPart in ipairs(entry.numberParts) do
            currentNumbers[numberPart] = true
            local fresh = self.originalProperties[numberPart] == nil
            local numberOriginal = self:_snapshot(numberPart)
            if playtest then
                self.selectionFilter:Restore(numberPart, numberOriginal.collisionGroup)
                StudioPlotsPartPolicy.Play(numberPart, numberOriginal,
                    self.state == 2, false, VOLUME_COLOR, VOLUME_ALPHA)
            else
                StudioPlotsPartPolicy.Edit(numberPart, numberOriginal, self.state == 2)
                if self.state == 2 then
                    self.selectionFilter:Restore(numberPart, numberOriginal.collisionGroup)
                else
                    self.selectionFilter:Hide(numberPart, numberOriginal.collisionGroup)
                end
                if fresh then numberPart.LocalTransparencyModifier = 1 end
                self:_fade(numberPart, "LocalTransparencyModifier",
                    if self.state == 2 then numberOriginal.localTransparency else 1)
            end
        end
    end

    for volume, _ in pairs(self.volumeParts) do
        if not currentVolumes[volume] then
            self:_restore(volume)
            local overlay = self.overlays[volume]
            if overlay then
                self:_cancel(overlay)
                overlay:Destroy()
                self.overlays[volume] = nil
            end
            local connection = self.sizeConnections[volume]
            if connection then connection:Disconnect() end
            self.sizeConnections[volume] = nil
        end
    end
    for part, _ in pairs(self.numberParts) do
        if not currentNumbers[part] then self:_restore(part) end
    end
    self.volumeParts = currentVolumes
    self.numberParts = currentNumbers
    if not playtest then self:_removeHiddenSelection() end
    return #entries, missingVolumes, missingNumbers
end

function PlotsVisibility:Next()
    if self.destroyed then return end
    if self.phase ~= "edit" then
        warn("[game1][plots] Plots preview works only in Studio Edit mode")
        return
    end
    local nextState = (self.state + 1) % 3
    local plots = self.workspace:FindFirstChild("Plots")
    if not plots or not plots:IsA("Folder") then
        warn("[game1][plots] Workspace.Plots folder not found")
        return
    end
    self.state = nextState
    self.button:SetActive(nextState ~= 0)
    local volumes, missingVolumes, missingNumbers = self:_refresh()
    if volumes == 0 then
        self.state = 0
        self.button:SetActive(false)
        warn("[game1][plots] No plot volumes found in Workspace.Plots/01..50")
        return
    end
    print(("[game1][plots] %s · volumes=%d · missing volumes=%d · missing numbers=%d")
        :format(({"hidden", "volumes", "volumes + numbers"})[nextState + 1], volumes, missingVolumes, missingNumbers))
end

function PlotsVisibility:_release()
    for instance, tween in pairs(self.tweens) do
        self.tweens[instance] = nil
        tween:Cancel()
    end
    for part, original in pairs(self.originalProperties) do
        self.selectionFilter:Restore(part, original.collisionGroup)
        StudioPlotsPartPolicy.Restore(part, original)
    end
    table.clear(self.originalProperties)
    for _, connection in pairs(self.sizeConnections) do connection:Disconnect() end
    table.clear(self.sizeConnections)
    for _, overlay in pairs(self.overlays) do overlay:Destroy() end
    table.clear(self.overlays)
    table.clear(self.volumeParts)
    table.clear(self.numberParts)
end

function PlotsVisibility:Destroy()
    if self.destroyed then return end
    self.destroyed = true
    self:_release()
    for _, connection in ipairs(self.connections) do connection:Disconnect() end
    table.clear(self.connections)
end

return table.freeze(PlotsVisibility)
