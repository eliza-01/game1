local HttpService = game:GetService("HttpService")
local StudioService = game:GetService("StudioService")

local toolbar = plugin:CreateToolbar("NewPlace")
local button = toolbar:CreateButton("Control Center", "Check the NewPlace local Control Center host agent", "")
button.ClickableWhenViewportHidden = true

local URL = "http://127.0.0.1:43821/api/agent/info"
local TOKEN = "NewPlaceLocalControlV1"

local function checkAgent()
    local ok, response = pcall(HttpService.RequestAsync, HttpService, {
        Url = URL,
        Method = "GET",
        Headers = { ["X-Control-Token"] = TOKEN },
    })
    if not ok then
        warn("[NewPlace Plugin] Control Center agent is unavailable: " .. tostring(response))
        return
    end
    if not response.Success then
        warn(("[NewPlace Plugin] Agent HTTP %d: %s"):format(response.StatusCode, response.Body))
        return
    end
    local decodedOk, data = pcall(HttpService.JSONDecode, HttpService, response.Body)
    if decodedOk then
        print(("[NewPlace Plugin] Connected · %s · %s"):format(tostring(data.project), tostring(data.build)))
    else
        print("[NewPlace Plugin] Connected")
    end
end
button.Click:Connect(checkAgent)
print("[NewPlace Plugin] loaded")
