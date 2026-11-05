-- M216: reject legacy global commands (including M215) before they can mutate.
return function(config: any)
    return function(command: any)
        if command.project ~= "game1" or command.schemaVersion ~= 6
            or type(command.operationId) ~= "string" or command.operationId == ""
            or type(command.targetSlug) ~= "string" or command.targetSlug == ""
            or type(command.bindingRevision) ~= "number" or command.bindingRevision < 1
            or type(command.modelAssetId) ~= "string" or command.modelAssetId == ""
            or type(command.atlasAssetId) ~= "string" or command.atlasAssetId == "" then
            warn("[game1] rejected unsafe/unscoped Location Asset sync command")
            return
        end
        local ok, report, refreshError = pcall(function()
            if config.RunService:IsRunning() then
                error("Studio Edit mode required")
            end
            return config.decoManager:refreshRegistry(
                command.targetSlug, true, command.modelAssetId, command.atlasAssetId)
        end)
        local payload = {
            project = "game1", command = "deco-refresh", schemaVersion = 6,
            operationId = command.operationId, targetSlug = command.targetSlug,
            bindingRevision = command.bindingRevision,
        }
        if ok and report ~= nil then
            for _, field in ipairs({ "models", "parts", "replacedModels", "matchedModels",
                "modelReferences", "pendingGeometry", "geometryUpdated", "meshPartsUpdated", "registryItems", "changes", "instances" }) do
                payload[field] = report[field]
            end
        else
            payload.error = tostring(if ok then refreshError else report)
        end
        local posted, response = pcall(config.HttpService.RequestAsync, config.HttpService, {
            Url = config.bridgeUrl .. "/deco-refresh-result", Method = "POST",
            Headers = { ["X-Game1-Token"] = config.bridgeToken,
                ["Content-Type"] = "application/json" },
            Body = config.HttpService:JSONEncode(payload),
        })
        if not posted or not response.Success then
            warn("[game1] Location Asset sync result could not be reported: " .. tostring(if posted then response.Body else response))
        end
    end
end
