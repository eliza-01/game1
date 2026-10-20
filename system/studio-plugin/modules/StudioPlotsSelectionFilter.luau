-- Studio viewport hit-test filter for hidden Plots authoring geometry.
-- Uses Roblox's documented StudioSelectable convention, not Locked/CanQuery.
-- Keeps all parts in Workspace with original CFrame, Size and welds intact.
local Filter = {}
Filter.__index = Filter

local STUDIO_GROUP = "StudioSelectable"
local HIDDEN_GROUP = "Game1PlotsPreviewHidden"
local ORIGINAL_GROUP_ATTRIBUTE = "__Game1PlotsOriginalCollisionGroup"

function Filter.OriginalGroup(part: BasePart): string
    -- An interrupted Studio session might have saved a hidden plot volume.
    -- Recover its previous group rather than treating the preview group as authored.
    local preserved = part:GetAttribute(ORIGINAL_GROUP_ATTRIBUTE)
    if type(preserved) == "string" and preserved ~= "" then
        return preserved
    end
    return part.CollisionGroup
end

function Filter.new(physicsService: any)
    return setmetatable({
        physicsService = physicsService,
        ready = false,
        failed = false,
    }, Filter)
end

function Filter:_configure(): boolean
    if self.ready then return true end
    if self.failed then return false end
    local ok, err = pcall(function()
        if not self.physicsService:IsCollisionGroupRegistered(STUDIO_GROUP) then
            self.physicsService:RegisterCollisionGroup(STUDIO_GROUP)
        end
        if not self.physicsService:IsCollisionGroupRegistered(HIDDEN_GROUP) then
            self.physicsService:RegisterCollisionGroup(HIDDEN_GROUP)
        end
        -- Only Editor selection collides with this group differently.
        -- All gameplay collision pairs retain their default configuration.
        if self.physicsService:CollisionGroupsAreCollidable(STUDIO_GROUP, HIDDEN_GROUP) then
            self.physicsService:CollisionGroupSetCollidable(STUDIO_GROUP, HIDDEN_GROUP, false)
        end
    end)
    if not ok then
        self.failed = true
        warn("[game1][plots] StudioSelectable filter unavailable: " .. tostring(err))
        return false
    end
    self.ready = true
    return true
end

function Filter:Hide(part: BasePart, originalGroup: string): boolean
    if not self:_configure() then return false end
    if part.CollisionGroup == HIDDEN_GROUP then return true end
    local ok, err = pcall(function()
        -- The attribute supports recovery after an unexpected editor shutdown.
        part:SetAttribute(ORIGINAL_GROUP_ATTRIBUTE, originalGroup)
        part.CollisionGroup = HIDDEN_GROUP
    end)
    if not ok then
        warn("[game1][plots] Cannot filter " .. part.Name .. ": " .. tostring(err))
        return false
    end
    return true
end

function Filter:Restore(part: BasePart, originalGroup: string)
    local stored = part:GetAttribute(ORIGINAL_GROUP_ATTRIBUTE)
    if part.CollisionGroup ~= HIDDEN_GROUP and stored == nil then return end
    local restoreTo = if type(stored) == "string" and stored ~= "" then stored else originalGroup
    local ok, err = pcall(function()
        if part.CollisionGroup == HIDDEN_GROUP then
            part.CollisionGroup = restoreTo
        end
        part:SetAttribute(ORIGINAL_GROUP_ATTRIBUTE, nil)
    end)
    if not ok then
        warn("[game1][plots] Cannot restore " .. part.Name .. " collision group: " .. tostring(err))
    end
end

return table.freeze(Filter)
