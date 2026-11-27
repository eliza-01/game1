--!strict
-- Roster presentation/selection only. The server owns IDs and persistence.
local Language = require(script.Parent.Parent:WaitForChild("localization"):WaitForChild("LanguageState"))
local View = {}
function View.Index(characters: {any}, id: string?): number?
    for i, record in ipairs(characters) do if record.id == id then return i end end
    return nil
end
function View.Adjacent(characters: {any}, id: string?, direction: number): string?
    local index = View.Index(characters, id)
    if not index or #characters < 2 then return nil end
    return characters[(index - 1 + direction) % #characters + 1].id
end
local function enable(button: TextButton, enabled: boolean)
    button.Active = enabled
    button.Interactable = enabled
    button.Selectable = enabled
    button.AutoButtonColor = enabled
    button.TextTransparency = if enabled then 0 else 0.45
end
function View.Render(controls: any, stage: string, characters: {any}, id: string?, limit: number,
    busy: boolean, confirming: boolean, canCancel: boolean)
    local selection = stage == "selection"
    local index = View.Index(characters, id)
    local known = index ~= nil
    controls.panel:SetAttribute("RosterCanCancel", canCancel)
    controls.newCharacter.Text = Language.Translate(if confirming or stage == "creation" then "feedback.cancel" else "creation.new_character")
    enable(controls.newCharacter, not busy and (if selection then known and (confirming or #characters < limit) else canCancel))
    controls.deleteCharacter.Text = Language.Translate(if confirming then "creation.confirm_delete" else "creation.delete_character")
    enable(controls.deleteCharacter, selection and not busy and known)
    controls.previousCharacter.Visible = selection and #characters > 1
    controls.nextCharacter.Visible = controls.previousCharacter.Visible
    enable(controls.previousCharacter, not busy and known and not confirming)
    enable(controls.nextCharacter, not busy and known and not confirming)
    if selection and index then controls.selectionCaption.Text = tostring(index) .. "/" .. tostring(#characters) .. "  ·  " .. tostring(#characters) .. "/" .. tostring(limit) end
    if confirming then controls.status.Text = Language.Translate("creation.delete_warning") end
end
return table.freeze(View)
