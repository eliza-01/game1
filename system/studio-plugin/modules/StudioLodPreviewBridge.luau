-- Read-only local Host Agent -> replicated Studio Play configuration.
-- Never writes the editable Place or a compiled Runtime manifest.
return function(services)
    local run = services.RunService
    local storage = services.ReplicatedStorage
    local http = services.HttpService
    local alive = true
    local marker = nil
    local digest = nil
    local lastWarning = nil
    local function warnOnce(message)
        if message ~= lastWarning then
            lastWarning = message
            warn("[game1][LOD preview] " .. message .. "; keeping last valid profile")
        end
    end
    local function clear()
        if marker then marker:Destroy(); marker = nil end
        digest = nil
        lastWarning = nil
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
                    local decoded, data = pcall(http.JSONDecode, http, response.Body)
                    if not decoded or type(data) ~= "table" then
                        warnOnce("invalid profile JSON")
                    elseif data.schemaVersion ~= 2 then
                        warnOnce("unsupported profile schema " .. tostring(data.schemaVersion) .. " (expected 2); check Control Center / Studio Bridge revisions")
                    elseif type(data.digest) ~= "string" then
                        warnOnce("profile digest missing")
                    elseif data.digest ~= digest or not marker or marker.Parent ~= storage then
                        lastWarning = nil
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
                    else
                        lastWarning = nil
                    end
                elseif alive and run:IsRunning() then
                    warnOnce("Control Center unavailable or profile exceeds size limit")
                end
            else
                clear()
            end
            task.wait(3)
        end
    end)
end
