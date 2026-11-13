--!strict
-- Studio Play folder -> authenticated local Control Center. Drafts only, never Save.
-- Both camera and HP use this one transport; changes are debounced per folder.
return function(services)
    local ReplicatedStorage = services.ReplicatedStorage
    local RunService = services.RunService
    local HttpService = services.HttpService
    local token = services.agentToken
    local specs = {
        Game1CameraDebug = {route="/api/options/camera-draft", maxBytes=2000},
        Game1HealthUiDebug = {route="/api/options/health-ui-draft", maxBytes=8000},
    }
    for name, spec in pairs(specs) do
        local current: Folder? = nil
        local changed: RBXScriptConnection? = nil
        local generation = 0
        local function disconnect()
            if changed then changed:Disconnect(); changed=nil end
            current=nil
            generation += 1
        end
        local function attach(folder: Folder)
            if current == folder then return end
            disconnect()
            current=folder
            changed=folder:GetAttributeChangedSignal("Payload"):Connect(function()
                if not RunService:IsStudio() or not RunService:IsRunning() then return end
                local payload=folder:GetAttribute("Payload")
                if type(payload)~="string" or #payload > spec.maxBytes then return end
                local ok, parsed=pcall(HttpService.JSONDecode,HttpService,payload)
                if not ok or type(parsed)~="table" then return end
                generation += 1
                local thisGeneration=generation
                task.delay(0.3,function()
                    if generation~=thisGeneration or current~=folder then return end
                    local sent,response=pcall(HttpService.RequestAsync,HttpService,{
                        Url=services.agentBaseUrl .. spec.route, Method="POST",
                        Headers={["Content-Type"]="application/json",["X-Control-Token"]=token},
                        Body=payload,
                    })
                    if not sent or not response.Success then
                        warn("[game1][options] Could not send Studio "..name.." draft: " .. tostring(sent and response.Body or response))
                    end
                end)
            end)
        end
        ReplicatedStorage.ChildAdded:Connect(function(item)
            if item:IsA("Folder") and item.Name==name then attach(item) end
        end)
        local initial=ReplicatedStorage:FindFirstChild(name)
        if initial and initial:IsA("Folder") then attach(initial) end
        RunService:GetPropertyChangedSignal("RunState"):Connect(function()
            if not RunService:IsRunning() then
                disconnect()
            else
                local folder=ReplicatedStorage:FindFirstChild(name)
                if folder and folder:IsA("Folder") then attach(folder) end
            end
        end)
    end
end
