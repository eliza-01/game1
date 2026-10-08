local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local HitSparkBurst = require(script.Parent:WaitForChild("HitSparkBurst"))
local HitFrontFlash = require(script.Parent:WaitForChild("HitFrontFlash"))

local WeaponBounceEffectPool = {}
WeaponBounceEffectPool.__index = WeaponBounceEffectPool

local function makeSlot(parent: Instance, config: any, index: number): any
    return {
        sparks = HitSparkBurst.Create(parent, config, index),
        flash = HitFrontFlash.Create(parent, config, index),
    }
end

function WeaponBounceEffectPool.new(effectConfig: any, poolSize: number): any
    local folder = Instance.new("Folder")
    folder.Name = "_Game1LocalWeaponBounceEffects"
    folder.Archivable = false
    folder.Parent = Workspace

    local count = math.max(1, math.floor(tonumber(poolSize) or 1))
    local slots = table.create(count)
    for index = 1, count do
        slots[index] = makeSlot(folder, effectConfig, index)
    end

    local self = setmetatable({
        _config = effectConfig,
        _slots = slots,
        _cursor = 0,
    }, WeaponBounceEffectPool)

    RunService.RenderStepped:Connect(function(dt)
        for _, slot in ipairs(slots) do
            HitSparkBurst.Step(slot.sparks, dt)
        end
    end)
    return self
end

function WeaponBounceEffectPool:Emit(position: Vector3, normal: Vector3, cameraCFrame: CFrame)
    self._cursor = (self._cursor % #self._slots) + 1
    local slot = self._slots[self._cursor]
    local sourcePosition = position + normal * 2
    HitSparkBurst.Emit(slot.sparks, self._config, position, cameraCFrame, false)
    HitFrontFlash.Emit(slot.flash, self._config, position, sourcePosition, cameraCFrame, false)
end

return WeaponBounceEffectPool
