-- One-shot authenticated command through the existing Edit bridge.
local Capture = require(script.Parent.StudioHitboxAssetCapture)
return function(services)
    return function(data)
        local result = {project = data.project, command = data.command, schemaVersion = data.schemaVersion,
            operationId = data.operationId, kind = data.kind, slug = data.slug,
            fullFingerprint = data.fullFingerprint, modelId = data.modelId}
        local ok, capture = pcall(function()
            assert(not services.RunService:IsRunning() and data.project == "game1" and data.schemaVersion == 1,
                "hitbox capture requires Studio Edit")
            return Capture.Run(data)
        end)
        if ok then result.capture = capture else result.error = tostring(capture):sub(1, 1500) end
        local encodedOK, encoded = pcall(function() return services.HttpService:JSONEncode(result) end)
        if not encodedOK or #encoded > 1900000 then
            result.capture = nil
            result.error = "hitbox capture exceeds bridge transport budget or cannot be encoded"
            encoded = services.HttpService:JSONEncode(result)
        end
        local sent, response = pcall(function()
            return services.HttpService:RequestAsync({Url = services.bridgeUrl .. "/hitbox-capture-result", Method = "POST",
                Headers = {["X-Game1-Token"] = services.bridgeToken, ["Content-Type"] = "application/json"}, Body = encoded})
        end)
        if not sent or not response.Success then warn("[game1] hitbox capture response failed: " .. tostring(response)) end
    end
end
