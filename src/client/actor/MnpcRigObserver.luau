-- Both local attack composers bind only to a live FULL visual generation.
-- Streaming and server-side release/reacquire may replace it without respawn.
local Observer = {}
function Observer.Watch(folder, entries, bind, unbind)
    local watched = {}
    local function remove(model)
        local state = watched[model]
        if not state then return end
        watched[model] = nil
        for _, connection in ipairs(state.connections) do connection:Disconnect() end
        unbind(model)
    end
    local function add(model)
        if not model:IsA("Model") or watched[model] then return end
        local state = {connections = {}, pending = false}
        watched[model] = state
        local function refresh()
            local entry = entries[model]
            local rig = model:FindFirstChild("ImportedRig")
            local root = model:FindFirstChild("HumanoidRootPart")
            local stage = model:GetAttribute("Game1MnpcLocalLod")
            local ready = model:GetAttribute("Game1MnpcRigReady") == true
                and (stage == nil or stage == "FULL") and rig and root
            if entry and (not ready or entry.visual ~= rig or entry.root ~= root) then unbind(model) end
            if ready and not entries[model] then bind(model) end
        end
        local function schedule()
            if state.pending then return end
            state.pending = true
            task.defer(function()
                state.pending = false
                if watched[model] == state then refresh() end
            end)
        end
        for _, attr in ipairs({"Game1MnpcRigReady", "Game1MnpcLocalLod", "Game1MonsterRuntime", "Game1NpcRuntime"}) do
            table.insert(state.connections, model:GetAttributeChangedSignal(attr):Connect(schedule))
        end
        table.insert(state.connections, model.ChildAdded:Connect(schedule))
        table.insert(state.connections, model.ChildRemoved:Connect(schedule))
        table.insert(state.connections, model.DescendantAdded:Connect(function(child)
            if child:IsA("Bone") then
                if entries[model] then unbind(model) end
                schedule()
            end
        end))
        table.insert(state.connections, model.DescendantRemoving:Connect(function(child)
            if child:IsA("Bone") and entries[model] then unbind(model); schedule() end
        end))
        schedule()
    end
    local added = folder.ChildAdded:Connect(add)
    local removed = folder.ChildRemoved:Connect(remove)
    local ancestry
    ancestry = folder.AncestryChanged:Connect(function()
        if folder.Parent then return end
        ancestry:Disconnect(); added:Disconnect(); removed:Disconnect()
        for model in pairs(watched) do remove(model) end
    end)
    for _, model in ipairs(folder:GetChildren()) do add(model) end
end
return table.freeze(Observer)
