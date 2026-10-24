local AssetService = game:GetService("AssetService")
local ChangeHistoryService = game:GetService("ChangeHistoryService")
local HttpService = game:GetService("HttpService")
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerStorage = game:GetService("ServerStorage")
local Selection = game:GetService("Selection")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

local LocationCommands = require(script.Parent.modules.LocationCommands)
local StudioMarkerVisibility = require(script.Parent.modules.StudioMarkerVisibility)
local StudioPlotsVisibility = require(script.Parent.modules.StudioPlotsVisibility)
local StudioDebugPreferenceBridge = require(script.Parent.modules.StudioDebugPreferenceBridge)
local StudioModelLoadCommands = require(script.Parent.modules.StudioModelLoadCommands)
local StudioActorSpawnCommands = require(script.Parent.modules.StudioActorSpawnCommands)
local StudioTimelineEditorCommands = require(script.Parent.modules.StudioTimelineEditorCommands)
local DecoManager = require(script.Parent.modules.DecoManager)
local StudioDecoSyncCommands = require(script.Parent.modules.StudioDecoSyncCommands)

local toolbar = plugin:CreateToolbar("game1")
local markerVisibility = StudioMarkerVisibility.new(plugin, toolbar, Workspace)
local plotsVisibility = StudioPlotsVisibility.new({
    plugin = plugin,
    toolbar = toolbar,
    Workspace = Workspace,
    CoreGui = game:GetService("CoreGui"),
    TweenService = game:GetService("TweenService"),
    RunService = RunService,
    Selection = Selection,
    PhysicsService = game:GetService("PhysicsService"),
})
local AGENT_BASE_URL = "http://127.0.0.1:43821"
local AGENT_URL = AGENT_BASE_URL .. "/api/agent/info"
local AGENT_TOKEN = "Game1LocalControlV1"
local BRIDGE_URL = "http://127.0.0.1:43137"
local BRIDGE_TOKEN = "Game1StudioBridgeV1"

local locationCommands = LocationCommands({
    HttpService = HttpService,
    Selection = Selection,
    Workspace = Workspace,
    UserInputService = UserInputService,
    BRIDGE_URL = BRIDGE_URL,
    BRIDGE_TOKEN = BRIDGE_TOKEN,
    plugin = plugin,
})

local decoManager = DecoManager.new({
    plugin = plugin,
    toolbar = toolbar,
    HttpService = HttpService,
    AssetService = AssetService,
    Workspace = Workspace,
    ServerStorage = ServerStorage,
    ChangeHistoryService = ChangeHistoryService,
    UserInputService = UserInputService,
    agentBaseUrl = AGENT_BASE_URL,
    agentToken = AGENT_TOKEN,
})

StudioDebugPreferenceBridge({
    plugin = plugin,
    ReplicatedStorage = ReplicatedStorage,
    RunService = RunService,
})

local function checkAgent()
    local ok, response = pcall(HttpService.RequestAsync, HttpService, {
        Url = AGENT_URL,
        Method = "GET",
        Headers = { ["X-Control-Token"] = AGENT_TOKEN },
    })
    if not ok then
        warn("[game1 plugin] control center agent is unavailable: " .. tostring(response))
        return
    end
    if not response.Success then
        warn(("[game1 plugin] agent http %d: %s"):format(response.StatusCode, response.Body))
        return
    end
    local decodedOk, data = pcall(HttpService.JSONDecode, HttpService, response.Body)
    if decodedOk then
        print(("[game1 plugin] connected · %s · %s"):format(tostring(data.project), tostring(data.build)))
    else
        print("[game1 plugin] connected")
    end
end


local handleModelLoad = StudioModelLoadCommands({
    AssetService = AssetService,
    HttpService = HttpService,
    ServerStorage = ServerStorage,
    bridgeUrl = BRIDGE_URL,
    bridgeToken = BRIDGE_TOKEN,
})

local handleMonsterSpawn = StudioActorSpawnCommands({
    plugin = plugin,
    HttpService = HttpService,
    Selection = Selection,
    ServerStorage = ServerStorage,
    UserInputService = UserInputService,
    Workspace = Workspace,
    bridgeUrl = BRIDGE_URL,
    bridgeToken = BRIDGE_TOKEN,
})

local handleTimelineEditor = StudioTimelineEditorCommands({
    plugin = plugin,
    AssetService = AssetService,
    AnimationClipProvider = game:GetService("AnimationClipProvider"),
    TweenService = game:GetService("TweenService"),
    HttpService = HttpService,
    UserInputService = UserInputService,
    agentBaseUrl = AGENT_BASE_URL,
    agentToken = AGENT_TOKEN,
    bridgeUrl = BRIDGE_URL,
    bridgeToken = BRIDGE_TOKEN,
})

local handleDecoRefresh = StudioDecoSyncCommands({
    HttpService = HttpService,
    decoManager = decoManager,
    RunService = RunService,
    bridgeUrl = BRIDGE_URL,
    bridgeToken = BRIDGE_TOKEN,
})

local function pollBridge()
    if RunService:IsRunning() then
        return
    end
    local ok, response = pcall(HttpService.RequestAsync, HttpService, {
        Url = BRIDGE_URL .. "/command",
        Method = "GET",
        Headers = { ["X-Game1-Token"] = BRIDGE_TOKEN },
    })
    if not ok or not response.Success then
        return
    end
    local decodeOk, data = pcall(HttpService.JSONDecode, HttpService, response.Body)
    if not decodeOk or type(data) ~= "table" then
        return
    end
    if data.command == "model-load" then
        handleModelLoad(data)
    elseif data.command == "monster-spawn" then
        handleMonsterSpawn(data)
    elseif data.command == "timeline-editor" then
        handleTimelineEditor(data)
    elseif data.command == "location-authoring" then
        locationCommands.handle(data)
    elseif data.command == "deco-refresh" then
        handleDecoRefresh(data)
    end
end

task.spawn(function()
    while true do
        pollBridge()
        task.wait(1)
    end
end)

print("[game1 plugin] loaded · model bridge v24 · DecoManager identity-only placement + environment bounce authoring + locations + viewport timeline pose sampler")
