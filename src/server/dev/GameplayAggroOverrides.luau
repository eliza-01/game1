-- Studio GP-only overrides; permanent defaults live in Database.
local Overrides = {}
local rows = {}
function Overrides.Set(name: string, radius: number, aggressive: boolean)
    rows[name] = {radius=radius, aggressive=aggressive}
end
function Overrides.Get(name: string): any
    return rows[name]
end
return table.freeze(Overrides)
