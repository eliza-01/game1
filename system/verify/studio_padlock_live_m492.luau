-- Run in Studio Play, SERVER Command Bar after the houses report ready.
-- Read-only: report actual published visual pivot vs imported bone world frame.
local count, bad = 0, 0
for _, folder in workspace:GetDescendants() do
    if not folder:IsA("Folder") or folder.Name ~= "Game1PadlockVisuals" then continue end
    local house = folder.Parent
    if not house then continue end
    for _, model in folder:GetChildren() do
        if not model:IsA("Model") then continue end
        local visual = model:FindFirstChild("padlock_02", true)
        local socket = nil
        for _, item in house:GetDescendants() do
            if item:IsA("Bone") and item.Name == model.Name and not item:IsDescendantOf(folder) then
                -- Prefer the copy under the actual door assembly, if present.
                if not socket or item:FindFirstAncestor("DoorAssembly") then socket = item end
            end
        end
        if not visual or not visual:IsA("MeshPart") or not socket then
            warn("m496: missing visual or bone", house:GetFullName(), model.Name)
            bad += 1
            continue
        end
        local frame, pivot = socket.TransformedWorldCFrame, visual:GetPivot()
        local pos = (frame.Position - pivot.Position).Magnitude
        local forward = frame.LookVector:Dot(pivot.LookVector)
        local up = frame.UpVector:Dot(pivot.UpVector)
        local right = frame.RightVector:Dot(pivot.RightVector)
        if count < 4 or pos > 0.001 or forward < 0.99999 or up < 0.99999 or right < 0.99999 then
            print("m496 padlock", house.Name, model.Name, "head_error", pos, "forward_dot", forward, "up_dot", up, "right_dot", right,
                "bone", frame, "pivot", pivot, "pivotOffset", visual.PivotOffset)
        end
        count += 1
        if pos > 0.001 or forward < 0.99999 or up < 0.99999 or right < 0.99999 then bad += 1 end
    end
end
print("m496 padlock live:", count, "checked;", bad, "mismatches")
assert(count > 0 and bad == 0, "No mounted locks or live transform mismatch")
