-- Read-only local Host Agent -> replicated Studio Play configuration.
-- Never writes the editable Place or a compiled Runtime manifest.
return function(services)
    local run = services.RunService
    local storage = services.ReplicatedStorage
    local http = services.HttpService
    local alive = true
    local marker = nil
    local digest = nil
    local warned = false
    local function clear()
        if marker then marker:Destroy(); marker = nil end
        digest = nil
        warned = false
    end
    services.plugin.Unloading:Connect(function() alive = false; clear() end)
    task.spawn(function()
        while alive do
            if run:IsStudio() and run:IsRunning() and run:IsServer()
                and not storage:FindFirstChild("Game1LocationRuntimeManifest") then
                local ok, response = pcall(http.RequestAsync, http, {
                    Url = services.agentBaseUrl .. "/api/lod-manager/studio-preview",
                    Method = "GET", Headers = {["X-Control-Token"] = services.agentToken},
                })
                if alive and run:IsRunning() and run:IsServer() and ok and response.Success
                    and #response.Body < 180000 then
                    warned = false
                    local decoded, data = pcall(http.JSONDecode, http, response.Body)
                    if decoded and type(data) == "table" and data.schemaVersion == 1
                        and type(data.digest) == "string" and data.digest ~= digest then
                        if not marker or marker.Parent ~= storage then
                            marker = Instance.new("StringValue")
                            marker.Name = "Game1StudioLodPreview"
                            marker.Value = response.Body
                            marker.Parent = storage
                        else
                            marker.Value = response.Body
                        end
                        digest = data.digest
                        print("[game1][LOD preview] saved profile " .. digest:sub(1, 12))
                    end
                elseif alive and run:IsRunning() and not warned then
                    warned = true
                    warn("[game1][LOD preview] Control Center unavailable; keeping last valid profile")
                end
            else
                clear()
            end
            task.wait(3)
        end
    end)
end
