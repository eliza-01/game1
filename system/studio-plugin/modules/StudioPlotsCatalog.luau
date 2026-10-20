-- Read-only discovery contract for authored Workspace.Plots/01..50.
-- Neither folder creation nor volume/number reparenting belongs to the preview.
local Catalog = {}

function Catalog.Collect(workspace: Workspace): ({any}, number, number)
    local plots = workspace:FindFirstChild("Plots")
    if not plots or not plots:IsA("Folder") then
        return {}, 50, 50
    end

    local numbersFolder = workspace:FindFirstChild("Numbers_1-50")
    local numbersRoot = numbersFolder and numbersFolder:FindFirstChild("Numbers_1_50")
    local entries = {}
    local missingVolumes = 0
    local missingNumbers = 0

    for index = 1, 50 do
        local folderName = string.format("%02d", index)
        local folder = plots:FindFirstChild(folderName)
        local volume = if folder and folder:IsA("Folder")
            then folder:FindFirstChild("plot_" .. folderName .. "_volume")
                or folder:FindFirstChild("plot_" .. tostring(index) .. "_volume")
            else nil
        if not volume or not volume:IsA("BasePart") then
            missingVolumes += 1
            missingNumbers += 1
            continue
        end

        -- The attach-numbers Command Bar script parents each numbered model to
        -- its volume. Keep supporting the original Numbers_1_50 source layout.
        local number = volume:FindFirstChild(tostring(index))
        if not number and numbersRoot then
            number = numbersRoot:FindFirstChild(tostring(index))
        end
        local numberParts = {}
        if number and number:IsA("Model") then
            for _, instance in ipairs(number:GetDescendants()) do
                if instance:IsA("BasePart") then
                    table.insert(numberParts, instance)
                end
            end
        end
        if #numberParts == 0 then missingNumbers += 1 end

        table.insert(entries, {
            index = index,
            volume = volume,
            numberParts = numberParts,
        })
    end

    return entries, missingVolumes, missingNumbers
end

return table.freeze(Catalog)
