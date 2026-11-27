local Shared=game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local options=table.clone(require(Shared:WaitForChild("GameOptions")).ExperimentalMonsterNavigation())
local combat=Shared:WaitForChild("combat")
local bowPolicy=require(combat:WaitForChild("BowProjectileConfig"))
local attackPolicy=require(combat:WaitForChild("AttackConfig"))
local balance=require(Shared:WaitForChild("balance"):WaitForChild("Balance"))
-- Retreat protects against a bow even when the target is currently unarmed.
-- Database owns effective weapon radii; projectile/aim limits are only caps.
local cap=math.min(bowPolicy.MaxDistance,attackPolicy.MaxAimDistance)
local bowRange=0
for _,weapon in ipairs(balance.Weapons) do
    if weapon.type=="bow" then
        bowRange=math.max(bowRange,math.clamp(weapon.radius,1,cap))
    end
end
assert(bowRange>0,"Monster navigation requires a bow in the balance database")
options.bowRange=bowRange
return table.freeze(options)
