--!strict
-- Temporary visual-only lift/rotation; navigation root stays on the floor.
local Presentation={}
function Presentation.Begin(model: Model): any
    local root=model:FindFirstChild("RootCollider")
    local weld=root and root:FindFirstChild("VisualRootWeld")
    if weld and weld:IsA("Weld") then return {weld=weld,base=weld.C0} end
    return nil
end
function Presentation.Step(pose: any, fraction: number, buff: boolean)
    if not pose or not pose.weld.Parent then return end
    local angle=2*math.pi*fraction
    local rotate=if buff then CFrame.Angles(0,angle,0) else CFrame.Angles(angle,0,0)
    pose.weld.C0=CFrame.new(0,3*math.sin(math.pi*fraction),0)*rotate*pose.base
end
function Presentation.Finish(pose: any)
    if pose and pose.weld.Parent then pose.weld.C0=pose.base end
end
return table.freeze(Presentation)
