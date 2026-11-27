-- Combat root precedence shared by Monster/NPC targeting and its broad phase.
-- Do not substitute the interaction root resolver: it has different eligibility.
local Root = {}
function Root.Get(model)
    if not model then return nil end
    local part = model:FindFirstChild("RootCollider") or model:FindFirstChild("HumanoidRootPart") or model.PrimaryPart
    if part and part:IsA("BasePart") then return part end
    return nil
end
return table.freeze(Root)
