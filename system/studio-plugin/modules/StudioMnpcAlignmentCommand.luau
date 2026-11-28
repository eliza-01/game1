-- Existing Edit bridge, separate result type and identity from assembly capture.
local Alignment = require(script.Parent.StudioMnpcImportAlignment)
return function(services)
    return function(data)
        local result = {}
        for _, key in {"project","command","schemaVersion","operationId","kind","slug","revision","expectedRevision",
            "fullFingerprint","sourceSha256","modelAssetId","imageAssetId"} do result[key]=data[key] end
        local ok, value = pcall(function()
            assert(not services.RunService:IsRunning() and data.project=="game1" and data.schemaVersion==1,
                "MNPC alignment requires Studio Edit and schema v1")
            return Alignment.Run(data)
        end)
        if ok then result.alignment=value else result.error=tostring(value):sub(1,1500) end
        local encodedOK, encoded = pcall(function() return services.HttpService:JSONEncode(result) end)
        if not encodedOK or #encoded>1900000 then
            result.alignment=nil
            result.error="MNPC import report cannot be encoded or exceeds 1.9 MB"
            encoded=services.HttpService:JSONEncode(result)
        end
        local sent,response=pcall(function()
            return services.HttpService:RequestAsync({Url=services.bridgeUrl.."/mnpc-align-result",Method="POST",
                Headers={["X-Game1-Token"]=services.bridgeToken,["Content-Type"]="application/json"},Body=encoded})
        end)
        if not sent or not response.Success then warn("[game1] MNPC alignment response failed: "..tostring(response)) end
    end
end
