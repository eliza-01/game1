--!strict
-- Studio plugin transport: Game1CameraDebug -> authenticated LOCAL agent draft.
-- It NEVER writes the persisted Options manifest, which needs an explicit Save.
return function(services)
    local ReplicatedStorage = services.ReplicatedStorage
    local RunService = services.RunService
    local HttpService = services.HttpService
    local endpoint = services.agentBaseUrl .. "/api/options/camera-draft"
    local token = services.agentToken
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
            if type(payload)~="string" or #payload > 2000 then return end
            local ok,parsed=pcall(HttpService.JSONDecode,HttpService,payload)
            if not ok or type(parsed)~="table" then return end
            generation += 1
            local thisGeneration=generation
            task.delay(0.3,function()
                if generation~=thisGeneration or current~=folder then return end
                local sent,response=pcall(HttpService.RequestAsync,HttpService,{
                    Url=endpoint,
                    Method="POST",
                    Headers={["Content-Type"]="application/json",["X-Control-Token"]=token},
                    Body=payload,
                })
                if not sent or not response.Success then
                    warn("[game1][camera] Could not send Studio camera draft: " .. tostring(sent and response.Body or response))
                end
            end)
        end)
    end
    ReplicatedStorage.ChildAdded:Connect(function(item)
        if item:IsA("Folder") and item.Name=="Game1CameraDebug" then attach(item) end
    end)
    local existing=ReplicatedStorage:FindFirstChild("Game1CameraDebug")
    if existing and existing:IsA("Folder") then attach(existing) end
    RunService:GetPropertyChangedSignal("RunState"):Connect(function()
        if not RunService:IsRunning() then
            disconnect()
        else
            local folder=ReplicatedStorage:FindFirstChild("Game1CameraDebug")
            if folder and folder:IsA("Folder") then attach(folder) end
        end
    end)
end
