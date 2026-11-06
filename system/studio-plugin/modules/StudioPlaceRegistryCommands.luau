-- M240: separate Studio Bridge controller, NOT an extension of DecoManager.
local Inventory=require(script.Parent.StudioPlaceRegistryInventory)
local Repair=require(script.Parent.StudioPlaceRegistryRepair)
local Sync=require(script.Parent.StudioPlaceRegistrySync)

return function(config: any)
    local session: any=nil
    return function(command: any)
        if command.project~="game1" or command.command~="location-place-registry"
            or command.schemaVersion~=1 or type(command.operationId)~="string"
            or type(command.catalog)~="table" or command.catalog.domain~="location_assets"
            or type(command.catalog.digest)~="string" then
            warn("[game1] rejected invalid Place Registry command")
            return
        end
        local phase=command.phase
        local ok,result=pcall(function()
            if config.RunService:IsRunning() then error("Studio Edit mode required") end
            if phase=="scan" then
                local scan=Inventory.Scan(config.Workspace,command.catalog,{
                    loader=config.decoManager.loader,
                })
                local token=config.HttpService:GenerateGUID(false)
                session={token=token,digest=command.catalog.digest,refs=scan.refs}
                local report={schemaVersion=1,placeId=scan.placeId,
                    placements=scan.placements,warnings=scan.warnings}
                return {scanToken=token,scan=report,inventory=scan.inventory}
            end
            if phase=="undo" then
                local oldId=command.undoOperationId
                if type(oldId)~="string" or not oldId:match("^[0-9a-f]+$")
                    or #oldId~=32 then error("invalid Place Registry undo identity") end
                local expected="G1PlaceRegistry:"..oldId
                local allowed,name=config.ChangeHistoryService:GetCanUndo()
                if allowed~=true or name~=expected then
                    error("Undo заблокирован: последняя операция Studio не совпадает с Place Registry. Сначала отмените новые изменения в Studio.")
                end
                config.ChangeHistoryService:Undo()
                session=nil
                return {result={changed=0,undone=true}}
            end
            if phase~="repair" and phase~="sync" and phase~="select" then
                error("unknown Place Registry phase")
            end
            if not session or command.scanToken~=session.token
                or command.catalog.digest~=session.digest then
                error("Place Registry Scan expired; scan again")
            end
            if type(command.keys)~="table" or #command.keys<1 or #command.keys>4096 then
                error("explicit scanned placement selection required")
            end
            local chosen,seen={},{}
            for _,key in ipairs(command.keys) do
                if type(key)~="string" or seen[key] or not session.refs[key] then
                    error("invalid/duplicate Place Registry key")
                end
                seen[key]=true
                local ref=session.refs[key]
                if not Inventory.Validate(ref) then
                    error("Place changed since scan ("..key.."); rescan before mutation")
                end
                table.insert(chosen,ref)
            end
            if phase=="select" then
                local selected,once={},{}
                for _,ref in ipairs(chosen) do
                    local target=ref.placement
                    if target.Parent and not once[target] then
                        once[target]=true
                        table.insert(selected,target)
                    end
                end
                if #selected==0 then error("no scanned objects still exist") end
                config.Selection:Set(selected)
                return {result={changed=0,selected=#selected}}
            end
            local ctx={http=config.HttpService,history=config.ChangeHistoryService,
                loader=config.decoManager.loader,
                recordingName="G1PlaceRegistry:"..command.operationId}
            local actionReport
            if phase=="repair" then
                local allRefs={}
                for _,ref in pairs(session.refs) do table.insert(allRefs,ref) end
                table.sort(allRefs,function(a,b) return a.row.key<b.row.key end)
                ctx.allRefs=allRefs
                actionReport=Repair.Apply(chosen,ctx)
            else
                actionReport=Sync.Apply(chosen,ctx)
            end
            session=nil -- Mutations always invalidate the read-only snapshot.
            return {result=actionReport}
        end)
        local payload={project="game1",command="location-place-registry",
            schemaVersion=1,operationId=command.operationId,phase=phase,
            catalogDigest=command.catalog.digest}
        if ok then
            for key,value in pairs(result) do payload[key]=value end
        else
            payload.error=tostring(result):sub(1,700)
        end
        local sent,response=pcall(config.HttpService.RequestAsync,config.HttpService,{
            Url=config.bridgeUrl.."/place-registry-result",Method="POST",
            Headers={["X-Game1-Token"]=config.bridgeToken,["Content-Type"]="application/json"},
            Body=config.HttpService:JSONEncode(payload),
        })
        if not sent or not response.Success then
            warn("[game1] Place Registry Bridge response failed: "..tostring(if sent then response.Body else response))
        end
    end
end
