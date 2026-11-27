-- Pure horizontal broad phase. Each record carries its GetPlayers order.
-- No height, health, territory, or collision filtering belongs here.
local Grid = {}
Grid.__index = Grid

function Grid.new(cellSize)
    assert(cellSize > 0)
    return setmetatable({size = cellSize, columns = {}, cells = {}, records = {}}, Grid)
end

local function finite(value)
    return value == value and math.abs(value) < math.huge
end

function Grid:Add(player, x, z)
    if not finite(x) or not finite(z) then return end
    local ix, iz = math.floor(x / self.size), math.floor(z / self.size)
    local column = self.columns[ix]
    if not column then column = {}; self.columns[ix] = column end
    local cell = column[iz]
    if not cell then
        cell = {x = ix, z = iz, records = {}}
        column[iz] = cell
        table.insert(self.cells, cell)
    end
    local record = {player = player, order = #self.records + 1}
    table.insert(self.records, record)
    table.insert(cell.records, record)
end

function Grid:Query(x, z, radius)
    if not finite(x) or not finite(z) or radius ~= radius or radius < 0 then return {} end
    local candidates = {}
    local function append(cell)
        if cell then
            for _, record in ipairs(cell.records) do table.insert(candidates, record) end
        end
    end
    if radius == math.huge then
        for _, record in ipairs(self.records) do table.insert(candidates, record) end
    else
        local minX, maxX = math.floor((x - radius) / self.size), math.floor((x + radius) / self.size)
        local minZ, maxZ = math.floor((z - radius) / self.size), math.floor((z + radius) / self.size)
        -- Large authored radii must not iterate huge numbers of empty cells.
        if (maxX - minX + 1) * (maxZ - minZ + 1) > #self.cells then
            for _, cell in ipairs(self.cells) do
                if cell.x >= minX and cell.x <= maxX and cell.z >= minZ and cell.z <= maxZ then append(cell) end
            end
        else
            for ix = minX, maxX do
                local column = self.columns[ix]
                if column then
                    for iz = minZ, maxZ do append(column[iz]) end
                end
            end
        end
        -- The old nearest loop uses <=, so the last equal-distance player wins.
        table.sort(candidates, function(a, b) return a.order < b.order end)
    end
    local players = {}
    for _, record in ipairs(candidates) do table.insert(players, record.player) end
    return players
end

return Grid
