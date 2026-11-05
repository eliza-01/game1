-- Explicitly authored house preview in Workspace.Plots/NN/Houses.
-- The placed copy is distinct from ServerStorage templates and player-owned houses.
-- Refuses to modify any object it did not create and mark itself.
local PlotsCatalog = require(script.Parent.StudioPlotsCatalog)
local HouseFrame = require(script.Parent.StudioRealEstateHouseFrame)

return function(context)
    local HttpService = context.HttpService
    local Workspace = context.Workspace
    local ServerStorage = context.ServerStorage
    local RunService = context.RunService
    local ChangeHistoryService = context.ChangeHistoryService

    local function findPlot(index: number): (Folder, BasePart)
        local entries = PlotsCatalog.Collect(Workspace)
        for _, entry in ipairs(entries) do
            if entry.index == index then
                local folder = entry.volume.Parent
                if folder and folder:IsA("Folder") then
                    return folder, entry.volume
                end
            end
        end
        error(string.format("Workspace.Plots/%02d/plot_%02d_volume not found", index, index))
    end

    local function validateIdentity(command)
        if RunService:IsRunning() then
            error("House Place/Clear works only in Studio Edit Mode")
        end
        local slug = tostring(command.houseSlug or "")
        local index = command.plotIndex
        if slug == "" or slug:find("[^%w_%-]") then
            error("Invalid registered house slug")
        end
        if typeof(index) ~= "number" or index % 1 ~= 0 or index < 1 or index > 50 then
            error("Plot must be between 1 and 50")
        end
        return slug, index
    end

    -- One anchoring policy for staged previews and already placed previews.
    -- Checking *after* parenting matters: no successful Place may report Free
    -- while a descendant BasePart is actually anchored in Workspace.
    local function setAndVerifyAnchored(model: Model, anchored: boolean): number
        local count = 0
        for _, part in ipairs(model:GetDescendants()) do
            if part:IsA("BasePart") then
                part.Anchored = anchored
                count += 1
            end
        end
        if count == 0 then error("House preview has no BaseParts to anchor/free") end
        for _, part in ipairs(model:GetDescendants()) do
            if part:IsA("BasePart") and part.Anchored ~= anchored then
                error("House preview anchoring verification failed: " .. part:GetFullName())
            end
        end
        return count
    end

    -- Apply anchor state only to marked authored previews whose plot×house
    -- identities came from the server's saved binding snapshot.
    local function runAnchors(command)
        if RunService:IsRunning() then
            error("House Anchor/Free works only in Studio Edit Mode")
        end
        if typeof(command.anchored) ~= "boolean" or typeof(command.targets) ~= "table"
            or #command.targets > 250 then
            error("Invalid anchor command")
        end
        local wanted = {}
        local count = 0
        for _, item in ipairs(command.targets) do
            local slug = item.houseSlug
            local index = item.plotIndex
            if typeof(slug) ~= "string" or slug == "" or slug:find("[^%w_%-]")
                or typeof(index) ~= "number" or index % 1 ~= 0 or index < 1 or index > 50 then
                error("Invalid house/plot anchor target")
            end
            local key = tostring(index) .. ":" .. slug
            if wanted[key] then error("Duplicate house/plot anchor target") end
            wanted[key] = true
            count += 1
        end
        if count ~= #command.targets then error("Invalid anchor target collection") end
        local models = {}
        local parts = {}
        local plots = PlotsCatalog.Collect(Workspace)
        for _, entry in ipairs(plots) do
            local plotFolder = entry.volume.Parent
            local houses = plotFolder and plotFolder:FindFirstChild("Houses")
            if houses and houses:IsA("Folder") then
                for _, model in ipairs(houses:GetChildren()) do
                    if model:IsA("Model") and model:GetAttribute("Game1PlotHousePreview") == true
                        and model:GetAttribute("Game1PlotIndex") == entry.index then
                        local slug = model:GetAttribute("Game1RealEstateSlug")
                        if typeof(slug) == "string" and wanted[tostring(entry.index) .. ":" .. slug] then
                            table.insert(models, model)
                            for _, descendant in ipairs(model:GetDescendants()) do
                                if descendant:IsA("BasePart") then table.insert(parts, descendant) end
                            end
                        end
                    end
                end
            end
        end
        -- All validation is complete before any Workspace mutation.
        local recording = ChangeHistoryService:TryBeginRecording("Set authored house anchoring")
        if not recording then error("Studio undo recording unavailable; no changes made") end
        local previousParts, previousModels = {}, {}
        local ok, problem = pcall(function()
            for _, part in ipairs(parts) do
                previousParts[part] = part.Anchored
                part.Anchored = command.anchored
            end
            for _, part in ipairs(parts) do
                if part.Anchored ~= command.anchored then
                    error("Anchor/Free verification failed: " .. part:GetFullName())
                end
            end
            for _, model in ipairs(models) do
                previousModels[model] = model:GetAttribute("Game1PlotHouseAnchored")
                model:SetAttribute("Game1PlotHouseAnchored", command.anchored)
            end
        end)
        if not ok then
            for part, old in pairs(previousParts) do pcall(function() part.Anchored = old end) end
            for model, old in pairs(previousModels) do
                pcall(function() model:SetAttribute("Game1PlotHouseAnchored", old) end)
            end
            ChangeHistoryService:FinishRecording(recording, Enum.FinishRecordingOperation.Cancel)
            error("Anchor/Free failed (rolled back): " .. tostring(problem))
        end
        ChangeHistoryService:FinishRecording(recording, Enum.FinishRecordingOperation.Commit)
        return {status = "anchored", changed = #models, partsChanged = #parts,
                anchored = command.anchored}
    end

    -- Both single-row and bulk Place/Clear use these same preparation and
    -- commit functions. No placed objects are destroyed before all requested
    -- plots, templates and staged clones pass preflight.
    local function isManagedPreview(model, index)
        return model:IsA("Model")
            and model:GetAttribute("Game1PlotHousePreview") == true
            and model:GetAttribute("Game1PlotIndex") == index
            and typeof(model:GetAttribute("Game1RealEstateSlug")) == "string"
            and model:GetAttribute("Game1RealEstateSlug") == model.Name
    end

    local function checkedHousesFolder(plotFolder)
        local folder = plotFolder:FindFirstChild("Houses")
        if folder and not folder:IsA("Folder") then
            error("Plot Houses exists but is not a Folder")
        end
        return folder
    end

    local function managedChildren(folder, index)
        local existing = {}
        if folder then
            for _, child in ipairs(folder:GetChildren()) do
                if isManagedPreview(child, index) then
                    table.insert(existing, child)
                end
            end
        end
        return existing
    end

    local function rejectUnmanagedNameConflict(folder, index, slug)
        if not folder then return end
        for _, child in ipairs(folder:GetChildren()) do
            if child.Name == slug and (not child:IsA("Model")
                or child:GetAttribute("Game1PlotHousePreview") ~= true
                or not isManagedPreview(child, index)) then
                error("Refusing to replace an unmanaged house in this plot")
            end
        end
    end

    local function stagePlace(binding, slug, index, plotFolder, volume)
        local folder = checkedHousesFolder(plotFolder)
        rejectUnmanagedNameConflict(folder, index, slug)
        if typeof(binding) ~= "table" or binding.houseSlug ~= slug or binding.plotIndex ~= index
            or typeof(binding.localCFrame) ~= "table" or #binding.localCFrame ~= 12
            or typeof(binding.scale) ~= "number" or binding.scale <= 0
            or typeof(binding.revision) ~= "number"
            or typeof(binding.anchored) ~= "boolean" then
            error("Missing or invalid saved Placement binding (anchored must be boolean)")
        end
        -- M208 bindings lack an explicit house MeshPart authoring pivot.
        -- Preserve the old Model-pivot placement semantics for these records;
        -- never mistake their original CFrame for a calibrated house anchor.
        local legacyPivot = binding.houseAnchorLocalCFrame == nil
        if not legacyPivot and (typeof(binding.houseAnchorLocalCFrame) ~= "table"
            or #binding.houseAnchorLocalCFrame ~= 12) then
            error("Invalid saved house-anchor CFrame")
        end
        local components = {}
        local anchorComponents = {}
        for i = 1, 12 do
            if not legacyPivot then
                local anchorValue = binding.houseAnchorLocalCFrame[i]
                if typeof(anchorValue) ~= "number" or anchorValue ~= anchorValue
                    or math.abs(anchorValue) > 1e7 then
                    error("Invalid placement house-anchor CFrame component")
                end
                anchorComponents[i] = anchorValue
            end
            local component = binding.localCFrame[i]
            if typeof(component) ~= "number" or component ~= component or math.abs(component) > 1e7 then
                error("Invalid placement CFrame component")
            end
            components[i] = component
        end
        local templateRoot = ServerStorage:FindFirstChild("real_estate")
        local houseFolder = templateRoot and templateRoot:FindFirstChild(slug)
        local modelFolder = houseFolder and houseFolder:FindFirstChild("model")
        local template = modelFolder and modelFolder:FindFirstChild(slug)
        if not template or not template:IsA("Model") or template:GetAttribute("Game1RealEstateTemplate") ~= true then
            error("Sync entire house to ServerStorage/real_estate/" .. slug .. "/model first")
        end
        local clone = template:Clone()
        clone.Name = slug
        local prepared, problem = pcall(function()
            clone:ScaleTo(binding.scale)
            local desiredRoot = volume.CFrame * CFrame.new(table.unpack(components))
            local house = HouseFrame.Find(clone)
            if not house then
                error("Published house template must contain exactly one MeshPart named house")
            end
            -- Align the exact visual house frame captured at Bind, NOT the
            -- template wrapper's independently computed Model pivot.
            -- Calibrated bindings use the measured original house anchor.
            -- Legacy M208 bindings use the published clone's *own* offset;
            -- algebraically this is the pre-M229 clone:PivotTo(desiredRoot),
            -- but executed through our existing centralized HouseFrame.Align.
            local houseOffset = if legacyPivot
                then clone:GetPivot():ToObjectSpace(house:GetPivot())
                else CFrame.new(table.unpack(anchorComponents))
            local desiredHouse = desiredRoot * houseOffset
            HouseFrame.Align(clone, house, desiredHouse, "authored plot house")
            clone:SetAttribute("Game1RealEstateTemplate", nil)
            clone:SetAttribute("Game1PlotHousePreview", true)
            clone:SetAttribute("Game1PlotIndex", index)
            clone:SetAttribute("Game1RealEstateSlug", slug)
            clone:SetAttribute("Game1PlacementRevision", binding.revision)
            setAndVerifyAnchored(clone, binding.anchored)
            clone:SetAttribute("Game1PlotHouseAnchored", binding.anchored)
            clone:SetAttribute("Game1PlacementRotationMode",
                if legacyPivot then "legacy-model-pivot" else "house-anchor-v2")
        end)
        if not prepared then
            clone:Destroy()
            error("Preparing house preview failed: " .. tostring(problem))
        end
        local previousPreviews = managedChildren(folder, index)
        return {kind = "place", plotFolder = plotFolder, folder = folder,
            previous = previousPreviews, clone = clone, binding = binding,
            rotationMode = if legacyPivot then "legacy-model-pivot" else "house-anchor-v2"}
    end

    local function cleanupStaged(plans)
        for _, plan in ipairs(plans) do
            if plan.clone and plan.clone.Parent == nil then
                plan.clone:Destroy()
            end
        end
    end

    local function executePlans(plans, action)
        if #plans == 0 then
            return {status = action == "clear_all" and "cleared_all" or "already_clear",
                changed = 0}
        end
        local recording = ChangeHistoryService:TryBeginRecording(
            action == "place_all" and "Place all authored house previews"
            or action == "clear_all" and "Clear all authored house previews"
            or action == "place" and "Place authored house preview"
            or "Clear authored house preview")
        if not recording then
            cleanupStaged(plans)
            error("Studio undo recording unavailable; no changes made")
        end
        local createdFolders = {}
        local totalVerifiedParts = 0
        local placed, placeError = pcall(function()
            for _, plan in ipairs(plans) do
                if plan.kind == "place" then
                    local folder = plan.folder
                    if not folder then
                        folder = Instance.new("Folder")
                        folder.Name = "Houses"
                        folder.Parent = plan.plotFolder
                        table.insert(createdFolders, folder)
                        plan.folder = folder
                    end
                    local clone = plan.clone
                    local binding = plan.binding
                    clone.Parent = folder
                    local verifiedParts = setAndVerifyAnchored(clone, binding.anchored)
                    totalVerifiedParts += verifiedParts
                    clone:SetAttribute("Game1PlotHouseAnchored", binding.anchored)
                end
            end
        end)
        if not placed then
            for _, plan in ipairs(plans) do
                if plan.clone then plan.clone:Destroy() end
            end
            for _, folder in ipairs(createdFolders) do folder:Destroy() end
            ChangeHistoryService:FinishRecording(recording, Enum.FinishRecordingOperation.Cancel)
            error("House placement failed (no existing previews removed): " .. tostring(placeError))
        end
        local removed = 0
        for _, plan in ipairs(plans) do
            for _, previous in ipairs(plan.previous) do
                previous:Destroy()
                removed += 1
            end
        end
        ChangeHistoryService:FinishRecording(recording, Enum.FinishRecordingOperation.Commit)
        local placedCount, legacyCount = 0, 0
        for _, plan in ipairs(plans) do
            if plan.kind == "place" then
                placedCount += 1
                if plan.rotationMode == "legacy-model-pivot" then legacyCount += 1 end
            end
        end
        if action == "place_all" then
            return {status = "placed_all", changed = placedCount,
                replaced = removed, anchoredPartsVerified = totalVerifiedParts,
                legacyPlacements = legacyCount}
        elseif action == "clear_all" then
            return {status = "cleared_all", changed = removed}
        elseif action == "place" then
            local plan = plans[1]
            local verifiedParts = totalVerifiedParts
            return {status = "placed", changed = placedCount,
                revision = plan.binding.revision,
                anchored = plan.binding.anchored, anchoredPartsVerified = verifiedParts,
                rotationMode = plan.rotationMode,
                destination = plan.clone:GetFullName()}
        end
        return {status = "cleared", changed = removed}
    end

    local function runBatch(command)
        if RunService:IsRunning() then
            error("House Place all / Clear all works only in Studio Edit Mode")
        end
        if command.plotIndex ~= 0 or typeof(command.targets) ~= "table" then
            error("Invalid house placement batch command")
        end
        if command.action == "clear_all" then
            if command.houseSlug ~= "*" or #command.targets ~= 0 then
                error("Invalid Clear all scope")
            end
            local plots = PlotsCatalog.Collect(Workspace)
            if #plots ~= 50 then
                error("Clear all requires all 50 authored plot volumes; Workspace unchanged")
            end
            local plans = {}
            for _, entry in ipairs(plots) do
                local folder = checkedHousesFolder(entry.volume.Parent)
                local previous = managedChildren(folder, entry.index)
                if #previous > 0 then
                    table.insert(plans, {kind = "clear", previous = previous})
                end
            end
            return executePlans(plans, "clear_all")
        end
        if command.action ~= "place_all" then error("Unknown bulk house placement action") end
        local slug = command.houseSlug
        if typeof(slug) ~= "string" or slug == "" or slug:find("[^%w_%-]")
            or #command.targets < 1 or #command.targets > 50 then
            error("Invalid Place all house or target list")
        end
        local plotsByIndex = {}
        for _, entry in ipairs(PlotsCatalog.Collect(Workspace)) do
            plotsByIndex[entry.index] = entry
        end
        local seen, plans = {}, {}
        local ok, problem = pcall(function()
            for _, binding in ipairs(command.targets) do
                if typeof(binding) ~= "table" or binding.houseSlug ~= slug then
                    error("Place all target house mismatch")
                end
                local index = binding.plotIndex
                if typeof(index) ~= "number" or index % 1 ~= 0 or index < 1 or index > 50
                    or seen[index] then
                    error("Place all duplicate/invalid plot")
                end
                seen[index] = true
                local entry = plotsByIndex[index]
                if not entry or not entry.volume.Parent or not entry.volume.Parent:IsA("Folder") then
                    error(string.format("Workspace.Plots/%02d/plot_%02d_volume not found", index, index))
                end
                table.insert(plans, stagePlace(binding, slug, index, entry.volume.Parent, entry.volume))
            end
        end)
        if not ok then
            cleanupStaged(plans)
            error("Place all preflight failed (Workspace unchanged): " .. tostring(problem))
        end
        return executePlans(plans, "place_all")
    end

    local function run(command)
        if command.action == "anchors" then return runAnchors(command) end
        if command.action == "place_all" or command.action == "clear_all" then
            return runBatch(command)
        end
        local slug, index = validateIdentity(command)
        local plotFolder, volume = findPlot(index)
        local folder = checkedHousesFolder(plotFolder)
        rejectUnmanagedNameConflict(folder, index, slug)
        if command.action == "clear" then
            local previous = {}
            for _, child in ipairs(managedChildren(folder, index)) do
                if child.Name == slug then table.insert(previous, child) end
            end
            if #previous == 0 then return {status = "already_clear", changed = 0} end
            return executePlans({{kind = "clear", previous = previous}}, "clear")
        end
        if command.action ~= "place" then error("Unknown house placement action") end
        return executePlans({stagePlace(command.placement, slug, index, plotFolder, volume)}, "place")
    end

    return function(command)
        local response = {
            command = "house-placement-preview-v4", schemaVersion = 4,
            project = "game1", operationId = command.operationId,
            houseSlug = command.houseSlug, plotIndex = command.plotIndex,
            action = command.action,
            anchored = command.anchored,
        }
        local ok, result = pcall(function()
            if command.command ~= "house-placement-preview-v4" or command.schemaVersion ~= 4 then
                error("Incompatible house-placement-preview protocol; reinstall Game1Bridge")
            end
            return run(command)
        end)
        if ok then
            for key, value in result do response[key] = value end
        else
            response.error = tostring(result)
        end
        local posted, reply = pcall(HttpService.RequestAsync, HttpService, {
            Url = context.bridgeUrl .. "/house-placement-result", Method = "POST",
            Headers = { ["X-Game1-Token"] = context.bridgeToken,
                        ["Content-Type"] = "application/json" },
            Body = HttpService:JSONEncode(response),
        })
        if not posted or not reply.Success then
            warn("[game1][house placement preview] bridge response failed: "
                .. tostring(posted and reply.StatusCode or reply))
        end
    end
end
