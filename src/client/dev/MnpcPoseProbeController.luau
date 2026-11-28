-- Optional manual observation on two Studio clients. No production registration.
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local HttpService = game:GetService("HttpService")
local Probe = require(ReplicatedStorage.Game1Shared.dev.MnpcPoseProbe)
local Controller = {}
local running = false

function Controller.Observe(mode: string)
    Probe.AssertStudio()
    assert(RunService:IsClient(), "run in client command bar")
    assert(mode == "FULL" or mode == "NONE", "use FULL or NONE (no owned rig; not a published LOD1)")
    assert(not running, "observation already running")
    local world = assert(workspace:FindFirstChild(Probe.FolderName), "start server probe first")
    local templates = assert(ReplicatedStorage:FindFirstChild(Probe.FolderName), "missing templates")
    running = true
    task.spawn(function()
        local localRig: Model? = nil
        local ok, err = xpcall(function()
            for _, kind in ipairs({"Monster", "NPC"}) do
                local case = world:FindFirstChild(kind)
                if not case or case:GetAttribute("Ready") ~= true then
                    print("[MNPC627][client] " .. HttpService:JSONEncode({kind = kind, mode = mode, status = "SKIPPED_NOT_READY"}))
                    continue
                end
                local link = case:FindFirstChild("Carrier")
                local carrier = link and link:IsA("ObjectValue") and link.Value
                if not carrier or not carrier:IsA("Model") then
                    warn("[MNPC627][client] carrier not replicated: " .. kind)
                    continue
                end
                if mode == "FULL" then
                    local folder = assert(templates:FindFirstChild(kind))
                    local source = assert(folder:FindFirstChildOfClass("Model"))
                    localRig = source:Clone()
                    localRig.Parent = workspace
                    local _, track = Probe.Load(localRig, case:GetAttribute("AnimationId"))
                    assert(Probe.WaitLoaded(track), "local animation load timeout")
                    track:AdjustSpeed(1)
                end
                local carrierReport = Probe.Motion(carrier, 2)
                local visualReport = if localRig then Probe.Motion(localRig, 2) else {status = "NO_OWNED_RIG", animators = 0, meshes = 0, bones = 0}
                print("[MNPC627][client] " .. HttpService:JSONEncode({kind = kind, mode = mode,
                    carrier = carrierReport, ownedVisual = visualReport}))
                if localRig then localRig:Destroy(); localRig = nil end
            end
        end, debug.traceback)
        if localRig then localRig:Destroy() end
        running = false
        if not ok then warn("[MNPC627][client] " .. tostring(err)) end
    end)
end

return table.freeze(Controller)
