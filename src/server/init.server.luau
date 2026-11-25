-- CharacterAutoLoads must be disabled before any yielding service/bootstrap dependency.
-- No gameplay avatar may be created while the player is in creation/selection.
game:GetService("Players").CharacterAutoLoads = false
-- This must run before shared-manifest waits and service bootstrap. A published
-- authoring Place can otherwise replicate neon Location boundaries if startup
-- later fails or stalls. RuntimePlaceBuilder also strips this folder offline.
local authoringCleanup = require(script:WaitForChild("world"):WaitForChild("Game1AuthoringCleanupService"))
authoringCleanup.Start()

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local ProjectInfo = require(Shared:WaitForChild("ProjectInfo"))
local RuntimeVersion = require(Shared:WaitForChild("RuntimeVersion"))
local BootstrapRoot = script:WaitForChild("bootstrap")
local ServiceCatalog = require(BootstrapRoot:WaitForChild("ServiceCatalog"))
local ServiceBootstrap = require(BootstrapRoot:WaitForChild("ServiceBootstrap"))

print(("[game1][server] %s v%s · runtime %s")
    :format(ProjectInfo.Name, ProjectInfo.Version, RuntimeVersion.Version))

local _, coreHealthy = ServiceBootstrap.StartAll(ServiceCatalog.Build(script), function(name, result)
    -- Health is server-private. Do not replicate internal errors or expose a mutating remote.
    script:SetAttribute("Service_" .. name, result.status)
    if result.status ~= "ready" then
        warn(("[game1][bootstrap] %s %s: %s"):format(name, result.status, result.error or "unknown"))
    end
end)
script:SetAttribute("CoreServicesReady", coreHealthy)
if not coreHealthy then
    warn("[game1][bootstrap] critical startup incomplete; see service health attributes")
end
