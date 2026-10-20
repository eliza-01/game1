-- Transport-only adapter for DecoManager's existing registry/material refresh.
-- Never imports models into ServerStorage or modifies published asset identities.
return function(config: any)
    return function(command: any)
        if command.project ~= "game1" or command.schemaVersion ~= 1
            or type(command.operationId) ~= "string" or command.operationId == "" then
            warn("[game1] invalid deco-refresh command")
            return
        end
        local ok, report, refreshError = pcall(function()
            return config.decoManager:refreshRegistry()
        end)
        local payload = {
            project = "game1",
            command = "deco-refresh",
            schemaVersion = 1,
            operationId = command.operationId,
        }
        if ok and report ~= nil then
            payload.models = report.models
            payload.parts = report.parts
            payload.registryItems = report.registryItems
        else
            payload.error = tostring(if ok then refreshError else report)
        end
        local posted, response = pcall(config.HttpService.RequestAsync, config.HttpService, {
            Url = config.bridgeUrl .. "/deco-refresh-result",
            Method = "POST",
            Headers = {
                ["X-Game1-Token"] = config.bridgeToken,
                ["Content-Type"] = "application/json",
            },
            Body = config.HttpService:JSONEncode(payload),
        })
        if not posted or not response.Success then
            warn("[game1] deco-refresh result could not be reported: " .. tostring(if posted then response.Body else response))
        end
    end
end
