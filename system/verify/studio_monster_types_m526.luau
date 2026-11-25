-- Run in Studio server Command Bar after Rojo Sync, without entering GP.
local dev = game:GetService("ServerScriptService"):WaitForChild("Game1Server"):WaitForChild("dev")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Balance = require(Shared.balance.Balance)
local Config = require(Shared.character.CharacterConfig)
local Layout = require(dev.GameplayTestLayout)
local Approach = require(dev.GameplayTestApproach)
local origin = CFrame.new(236.646, -53.76, 49.04) * CFrame.Angles(0, math.rad(137.647), 0)
local spacing = 40
local layout = Layout.Build(origin, Balance.Monsters, Balance.MaxLevel, spacing, Vector3.new(3, 5, 3), 12)
assert(#layout.tracks == 2 and Balance.MaxLevel == 35)
local function feetToRoot(point) return point + Vector3.new(0, Config.RootAnchorOffset, 0) end
local count = 0
for _, row in ipairs(Balance.Monsters) do
    local slot = assert(layout.slots[row.id]); count += 1
    if row.type == "ranged" then
        local track = layout.tracks[2]
        local relative = track.top:PointToObjectSpace(slot.point)
        assert(math.abs(math.abs(relative.Z) - track.size.Z / 2 - row.attackRange) < 0.001)
        local model = Instance.new("Model")
        model:SetAttribute("GameplayTestKind", "line")
        model:SetAttribute("MonsterCombatType", "ranged")
        model:SetAttribute("GameplayTestApproachFrame", slot.approachFrame)
        model:SetAttribute("GameplayTestApproachSize", slot.approachSize)
        assert(Approach.Allows(model, slot.visit.Position), row.id .. " Go should activate lane")
        assert(not Approach.Allows(model, feetToRoot(track.top:PointToWorldSpace(Vector3.new(relative.X,0,0)))))
        assert(not Approach.Allows(model, feetToRoot(slot.approachFrame.Position + origin.RightVector * spacing)))
        model:SetAttribute("GameplayTestKind", "group")
        assert(Approach.Allows(model, feetToRoot(track.top.Position)))
        model:Destroy()
    else
        assert(slot.approachFrame == nil)
    end
end
assert(count == 70)
print("[M526] 70 slots, rotated frame, range offsets, Go, safe track, neighbouring lane and group checks passed")
