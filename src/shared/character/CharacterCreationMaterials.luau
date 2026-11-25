--!strict
-- One material per editable appearance category; pairs and compound hair share it.
local Materials = {}
Materials.Groups = table.freeze({"hair", "eyes", "eyebrows", "head"})
local slots = table.freeze({hair = "hair", eyes = "eye_l", eyebrows = "eyebrow_l", head = "head"})
local bySlot = table.freeze({hair = "hair", head = "head", eye_l = "eyes", eye_r = "eyes",
    eyebrow_l = "eyebrows", eyebrow_r = "eyebrows"})
function Materials.Slot(group: string): string?
    return (slots :: {[string]: string})[group]
end
function Materials.GroupForPart(slot: any, hairChannel: any): string?
    if type(hairChannel) == "string" then return "hair" end
    if type(slot) ~= "string" then return nil end
    return (bySlot :: {[string]: string})[slot]
end
return table.freeze(Materials)
