local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local GameOptions = require(Shared:WaitForChild("GameOptions"))

local CombatStateService = {}
local activationSerial = setmetatable({}, { __mode = "k" })

local function validModel(model: Model?): boolean
	return model ~= nil and model:IsA("Model") and model.Parent ~= nil
end

local function clearIfCurrent(model: Model, serial: number, expiresAt: number)
	if not validModel(model) or activationSerial[model] ~= serial then
		return
	end
	local currentUntil = tonumber(model:GetAttribute("CombatUntilServerTime")) or 0
	if currentUntil > expiresAt + 0.001 or Workspace:GetServerTimeNow() + 0.001 < currentUntil then
		return
	end
	model:SetAttribute("InCombat", false)
	model:SetAttribute("CombatState", "Peace")
	model:SetAttribute("CombatUntilServerTime", 0)
end

function CombatStateService.Activate(model: Model?)
	if not validModel(model) then
		return
	end
	local duration = GameOptions.CombatStateDurationSeconds()
	local serial = (activationSerial[model] or 0) + 1
	activationSerial[model] = serial
	local expiresAt = Workspace:GetServerTimeNow() + duration
	model:SetAttribute("InCombat", true)
	model:SetAttribute("CombatState", "Combat")
	model:SetAttribute("CombatUntilServerTime", expiresAt)
	if duration <= 0 then
		clearIfCurrent(model, serial, expiresAt)
		return
	end
	task.delay(duration + 0.03, function()
		clearIfCurrent(model, serial, expiresAt)
	end)
end

function CombatStateService.ActivatePair(attacker: Model?, target: Model?)
	if attacker then
		CombatStateService.Activate(attacker)
	end
	if target and target ~= attacker then
		CombatStateService.Activate(target)
	end
end

function CombatStateService.Clear(model: Model?)
	if not validModel(model) then
		return
	end
	activationSerial[model] = (activationSerial[model] or 0) + 1
	model:SetAttribute("InCombat", false)
	model:SetAttribute("CombatState", "Peace")
	model:SetAttribute("CombatUntilServerTime", 0)
end

return table.freeze(CombatStateService)
