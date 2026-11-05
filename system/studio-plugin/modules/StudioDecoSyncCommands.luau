-- M238: protocol 8 adds read-only per-row Studio selection and COL atlas exclusion.
return function(config: any)
    return function(command: any)
        if command.project~="game1" or command.schemaVersion~=9
            or type(command.operationId)~="string" or command.operationId==""
            or type(command.targetSlug)~="string" or command.targetSlug==""
            or type(command.bindingRevision)~="number" or command.bindingRevision<1
            or type(command.modelAssetId)~="string" or command.modelAssetId==""
            or type(command.atlasAssetId)~="string" or command.atlasAssetId==""
            or (command.phase~="scan" and command.phase~="select" and command.phase~="attach" and command.phase~="replace") then
            warn("[game1] rejected stale/unscoped Studio Mesh ID command")
            return
        end
        local ok, report, failure=pcall(function()
            if config.RunService:IsRunning() then error("Studio Edit mode required") end
            if command.phase=="scan" then
                if type(command.modelHistory)~="table" then error("Model history required") end
                return config.decoManager:previewMeshSync(command.targetSlug,
                    command.modelAssetId,command.atlasAssetId,command.bindingRevision,
                    command.modelHistory,command.modelMeshInventory)
            end
            if command.phase=="select" then
                if type(command.scanToken)~="string" or type(command.partKeys)~="table" then
                    error("Find Mesh IDs before Select in Studio")
                end
                return config.decoManager:selectMeshSyncPart(command.targetSlug,
                    command.modelAssetId,command.atlasAssetId,command.scanToken,
                    command.bindingRevision,command.partKeys)
            end
            if command.phase=="attach" then
                if type(command.scanToken)~="string" or type(command.partKey)~="string" then
                    error("Find Mesh IDs before linking historical Model")
                end
                return config.decoManager:attachHistoricalMeshSync(command.targetSlug,
                    command.modelAssetId,command.atlasAssetId,command.scanToken,
                    command.bindingRevision,command.partKey)
            end
            if type(command.scanToken)~="string" or type(command.selectedKeys)~="table" then
                error("Find Mesh IDs and select pending MeshParts first") end
            return config.decoManager:refreshRegistry(command.targetSlug,true,
                command.modelAssetId,command.atlasAssetId,command.scanToken,command.bindingRevision,
                command.selectedKeys)
        end)
        local payload={project="game1",command="deco-refresh",schemaVersion=9,
            operationId=command.operationId,targetSlug=command.targetSlug,
            bindingRevision=command.bindingRevision,phase=command.phase}
        if ok and report then
            local fields=if command.phase=="scan" then {
                "scanToken","mode","inventory","foundMeshParts","managedMeshParts",
                "unmanagedMeshParts","managedModels","texturePending","geometryPending",
                "meshPending","parts","expectedMeshIds"
            } elseif command.phase=="select" then {
                "selectedName","selectedPath","selectedCount"
            } else {
                "models","parts","replacedModels","matchedModels","modelReferences",
                "pendingGeometry","geometryUpdated","meshPartsUpdated","registryItems",
                "changes","instances","fullySynced"
            }
            for _, field in ipairs(fields) do payload[field]=report[field] end
        else
            payload.error=tostring(if ok then failure else report)
        end
        local sent,response=pcall(config.HttpService.RequestAsync,config.HttpService,{
            Url=config.bridgeUrl.."/deco-refresh-result",Method="POST",
            Headers={["X-Game1-Token"]=config.bridgeToken,["Content-Type"]="application/json"},
            Body=config.HttpService:JSONEncode(payload),
        })
        if not sent or not response.Success then
            warn("[game1] Mesh ID Sync result could not be reported: "..tostring(if sent then response.Body else response))
        end
    end
end
