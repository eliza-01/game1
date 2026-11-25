--!strict
-- Warm actual published MeshPart/texture content, not model asset IDs.
-- Each variant replaces one slot of the default recipe; independent slots
-- share identical mesh content across combinations. No Cartesian explosion.
local Request = require(script.Parent:WaitForChild("CharacterCreationRequest"))
local Preview = require(script.Parent:WaitForChild("CharacterCreationPreviewController"))
local Preloader = require(script.Parent:WaitForChild("CharacterCreationMeshPreloader"))
local Warm = {}
function Warm.Run(remote: RemoteFunction, catalog: any, defaults: {[string]: any}, current: () -> boolean, progress: (number) -> ()): boolean
    local queue = {}
    for _, id in ipairs({"human_male", "human_female"}) do
        local base = defaults[id]
        table.insert(queue, {id = id, choice = table.clone(base)})
        for _, group in ipairs({"hair", "head", "eyes", "eyebrows"}) do
            for _, row in ipairs((catalog[id] or {})[group] or {}) do
                if row.id ~= base[group] then
                    local choice = table.clone(base)
                    choice[group] = row.id
                    choice.colors = nil -- server resolves authored defaults for each variant
                    choice.materials = nil
                    table.insert(queue, {id = id, choice = choice})
                end
            end
        end
    end
    -- Leave room in the server's 32-template cache for actual combinations.
    local limit = math.min(#queue, 24)
    local deadline = os.clock() + 75
    local function alive(): boolean return current() and os.clock() < deadline end
    local failed, completed = 0, 0
    for index = 1, limit do
        if not alive() then break end
        local row = queue[index]
        local ok, response = Request.Invoke(remote, alive, 25, row.id, row.choice)
        local loaded = false
        if ok and type(response) == "table" and response.ok == true then
            local model = Preview.AwaitTemplate(response.template, alive)
            if model then
                loaded = Preloader.PreloadModel(model, alive, function(value)
                    if alive() then progress((completed + value) / #queue) end
                end)
            end
        end
        if not loaded then failed += 1 else completed += 1 end
        if current() then progress(completed / #queue) end
    end
    local complete = completed == #queue and failed == 0 and current()
    if current() and not complete then
        warn("[game1][character-creation] variant prewarm incomplete; on-demand preload remains enabled")
    end
    return complete
end
return table.freeze(Warm)
