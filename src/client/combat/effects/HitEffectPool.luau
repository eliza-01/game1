local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local HitSparkBurst = require(script.Parent:WaitForChild("HitSparkBurst"))
local HitFrontFlash = require(script.Parent:WaitForChild("HitFrontFlash"))

local HitEffectPool = {}
HitEffectPool.__index = HitEffectPool

local function makeSlot(parent: Instance, config: any, index: number): any
    return {
        sparks = HitSparkBurst.Create(parent, config, index),
        flash = HitFrontFlash.Create(parent, config, index),
    }
end

function HitEffectPool.new(config: any): any
    local folder = Instance.new("Folder")
    folder.Name = "_Game1LocalHitEffects"
    folder.Archivable = false
    folder.Parent = Workspace

    local slots = table.create(config.PoolSize)
    for index = 1, config.PoolSize do
        slots[index] = makeSlot(folder, config, index)
    end

    local self = setmetatable({
        _config = config,
        _folder = folder,
        _slots = slots,
        _cursor = 0,
    }, HitEffectPool)
    RunService.RenderStepped:Connect(function(dt)
        for _, slot in ipairs(slots) do
            HitSparkBurst.Step(slot.sparks, dt)
        end
    end)
    return self
end

function HitEffectPool:Emit(position: Vector3, sourcePosition: Vector3, critical: boolean, cameraCFrame: CFrame)
    self._cursor = (self._cursor % #self._slots) + 1
    local slot = self._slots[self._cursor]
    HitSparkBurst.Emit(slot.sparks, self._config, position, cameraCFrame, critical)
    HitFrontFlash.Emit(slot.flash, self._config, position, sourcePosition, cameraCFrame, critical)
end

return HitEffectPool
