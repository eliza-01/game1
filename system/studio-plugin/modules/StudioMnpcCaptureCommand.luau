-- Edit-mode one-shot command. No polling loop; uses the existing Bridge.
local Capture = require(script.Parent.StudioMnpcAssemblyCapture)
return function(services)
    return function(data)
        local result = {project = data.project, command = data.command, schemaVersion = data.schemaVersion,
            operationId = data.operationId, kind = data.kind, slug = data.slug,
            fullFingerprint = data.fullFingerprint, idleFingerprint = data.idleFingerprint,
            expectedRevision = data.expectedRevision}
        local ok, capture = pcall(function()
            assert(not services.RunService:IsRunning() and data.project == "game1" and data.schemaVersion == 1,
                "MNPC capture requires Studio Edit and schema v1")
            return Capture.Run(data)
        end)
        if ok then result.capture = capture else result.error = tostring(capture):sub(1, 1500) end
        local encodedOK, encoded = pcall(function() return services.HttpService:JSONEncode(result) end)
        if not encodedOK or #encoded > 1900000 then
            result.capture = nil
            result.error = "MNPC geometry capture cannot be encoded or exceeds 1.9 MB transport budget"
            encoded = services.HttpService:JSONEncode(result)
        end
        local sent, response = pcall(function()
            return services.HttpService:RequestAsync({Url = services.bridgeUrl .. "/mnpc-capture-result", Method = "POST",
                Headers = {["X-Game1-Token"] = services.bridgeToken, ["Content-Type"] = "application/json"},
                Body = encoded})
        end)
        if not sent or not response.Success then warn("[game1] MNPC capture response failed: " .. tostring(response)) end
    end
end
