-- One-shot surface refinement for a server-confirmed hitscan candidate.
-- The hitbox decides Head/Body damage. COL/MeshPart can supply optional
-- visual-only contact coordinates; there are no projectile-frame raycasts.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")
local MeshPhysics = require(ReplicatedStorage:WaitForChild("Game1Shared")
    :WaitForChild("world"):WaitForChild("MeshPhysicsCore"))
local Policy = require(ReplicatedStorage:WaitForChild("Game1Shared")
    :WaitForChild("combat"):WaitForChild("BowProjectileConfig"))

local Surface = {}

local function isCollider(part: BasePart): boolean
    return MeshPhysics.IsCollider(part.Name) or part:GetAttribute("Game1DecoPhysicsOnly") == true
end

local function isVisual(part: BasePart): boolean
    return part:IsA("MeshPart") and part.Transparency < 1
        and part.Name ~= "rig_carrier" and not isCollider(part)
        and part.Name ~= "RootCollider" and part.Name ~= "NavigationRoot"
        and part.Name ~= "HumanoidRootPart" and part.Name ~= "GroundSensorPart"
end

-- Only cast against the selected model's known parts. For NPC/monster skinned
-- MeshParts, CanQuery=false is intentional; a *single impact-time* brute-force
-- query sees their collision mesh without changing the rig's collision flags.
-- No workspace-wide brute-force queries or raycasts per projectile frame.
local function castParts(origin: Vector3, displacement: Vector3, candidates: { BasePart }, brute: boolean): any?
    if #candidates == 0 then return nil end
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Include
    params.FilterDescendantsInstances = candidates
    params.RespectCanCollide = false
    params.BruteForceAllSlow = brute
    local hit = Workspace:Raycast(origin, displacement, params)
    if not hit then return nil end
    return {Instance = hit.Instance, Position = hit.Position, Distance = hit.Distance}
end

local function castModel(model: Model, origin: Vector3, displacement: Vector3, visualScope: Model?): any?
    local colliders: { BasePart } = {}
    local visuals: { BasePart } = {}
    for _, item in ipairs(model:GetDescendants()) do
        if item:IsA("BasePart") then
            if isCollider(item) then
                table.insert(colliders, item)
            elseif isVisual(item) and (visualScope == nil or item:IsDescendantOf(visualScope)) then
                table.insert(visuals, item)
            end
        end
    end
    -- Explicit COL meshes take precedence over decorative skinned meshes.
    -- In a legacy asset without COL, query its actual MeshPart collision shape.
    return castParts(origin, displacement, colliders, false)
        or castParts(origin, displacement, colliders, true)
        or castParts(origin, displacement, visuals, true)
end

-- The visible geometry of an animated character is distinct from the bone-local
-- head/body hitboxes. The latter may extend beyond the skinned mesh. A bounded
-- correction avoids a cosmetic arrow jumping across a limb or to the pivot.
function Surface.ResolveEntity(entity: Model, origin: Vector3, direction: Vector3,
    hitboxDistance: number, maxDistance: number): any?
    if not entity.Parent or maxDistance <= 0 then return nil end
    local visual = entity:FindFirstChild("Visual") or entity:FindFirstChild("ImportedRig") or entity
    if not visual:IsA("Model") then return nil end
    -- A hitbox may sit slightly inside the visible mesh. Start just behind
    -- this swept step so a ray beginning INSIDE a MeshPart can still find its
    -- front collision surface. Never search farther than the current Range.
    local rewind = math.min(Policy.VisualSurfaceSearchAhead, maxDistance)
    local contact = castModel(entity, origin - direction * rewind,
        direction * (maxDistance + rewind), visual)
    if contact then
        contact.Distance -= rewind
        if math.abs(contact.Distance - hitboxDistance) <= Policy.VisualSurfaceTolerance then
            return contact
        end
    end
    return nil
end

-- Landscape Painter's query volume is only a discovery proxy. It does not
-- define a contact point. Use precisely the same geometry resolver as actors;
-- no box- or pivot-based fallback that could magnetize an arrow to empty space.
function Surface.Resolve(proxy: BasePart, origin: Vector3, displacement: Vector3): any?
    if proxy.Name ~= "LandscapeSwayTarget"
        or proxy:GetAttribute("Game1LandscapeSwayTarget") ~= true then return nil end
    local model = proxy.Parent
    if not model or not model:IsA("Model") or displacement.Magnitude <= 1e-6 then return nil end
    return castModel(model, origin, displacement)
end

return table.freeze(Surface)
