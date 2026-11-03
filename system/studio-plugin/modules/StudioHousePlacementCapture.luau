-- Read-only Studio authoring adapter. Selection and plot markers stay untouched.
-- No runtime ownership, no house assembly, no Workspace mutation.
local PlotsCatalog = require(script.Parent.StudioPlotsCatalog)

return function(context)
    local HttpService = context.HttpService
    local Selection = context.Selection
    local Workspace = context.Workspace
    local RunService = context.RunService
    local BRIDGE_URL = context.bridgeUrl
    local BRIDGE_TOKEN = context.bridgeToken

    local function components(cframe: CFrame): {number}
        return { cframe:GetComponents() }
    end

    local function capture(command)
        if RunService:IsRunning() then
            error("Stop Studio Play/Run before binding a house placement")
        end
        local houseSlug = tostring(command.houseSlug or "")
        local plotIndex = tonumber(command.plotIndex)
        if not plotIndex or plotIndex % 1 ~= 0 or plotIndex < 1 or plotIndex > 50 then
            error("Plot must be between 1 and 50")
        end
        if houseSlug == "" then
            error("Choose a registered house in Real Estate")
        end
        local chosen = Selection:Get()
        if #chosen ~= 1 or not chosen[1]:IsA("Model") then
            error("Select exactly one Model named " .. houseSlug .. " in Studio Explorer")
        end
        local model = chosen[1] :: Model
        if model.Name ~= houseSlug or not model:IsDescendantOf(Workspace) then
            error("Selected Model must be Workspace model named exactly " .. houseSlug)
        end
        if not model:FindFirstChildWhichIsA("BasePart", true) then
            error("Selected house Model has no BasePart geometry")
        end
        local entries = PlotsCatalog.Collect(Workspace)
        local volume = nil
        for _, entry in ipairs(entries) do
            if entry.index == plotIndex then
                volume = entry.volume
                break
            end
        end
        if not volume then
            error(string.format("Workspace.Plots/%02d/plot_%02d_volume not found", plotIndex, plotIndex))
        end
        local world = model:GetPivot()
        local plotFrame = volume.CFrame
        return {
            houseSlug = houseSlug,
            plotIndex = plotIndex,
            plotVolume = volume.Name,
            worldCFrame = components(world),
            plotCFrame = components(plotFrame),
            localCFrame = components(plotFrame:ToObjectSpace(world)),
            scale = model:GetScale(),
        }
    end

    return function(command)
        local response = {
            command = "house-placement-capture", schemaVersion = 1,
            project = "game1", operationId = command.operationId,
            houseSlug = command.houseSlug, plotIndex = command.plotIndex,
        }
        local ok, result = pcall(capture, command)
        if ok then
            for field, value in pairs(result) do
                response[field] = value
            end
        else
            response.error = tostring(result)
        end
        local posted, answer = pcall(HttpService.RequestAsync, HttpService, {
            Url = BRIDGE_URL .. "/house-placement-result",
            Method = "POST",
            Headers = {
                ["X-Game1-Token"] = BRIDGE_TOKEN,
                ["Content-Type"] = "application/json",
            },
            Body = HttpService:JSONEncode(response),
        })
        if not posted or not answer.Success then
            warn("[game1][house placement] bridge failed: " .. tostring(posted and answer.StatusCode or answer))
        end
    end
end
