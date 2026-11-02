--!strict
-- Studio-only single-track animation player, one independent state per stand.
-- Never writes Player.Character, combat, gameplay animation state or registry data.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("character")
local Catalog = require(Shared:WaitForChild("CharacterStandAnimationCatalog"))
local Registry = require(Shared:WaitForChild("CharacterAnimationRegistry"))

local Playback = {}

function Playback.Bind(stand: Model, prompt: ProximityPrompt): () -> ()
    local profileId = tostring(stand:GetAttribute("Game1AnimationProfileId") or "")
    local profile = Registry.profiles and Registry.profiles[profileId]
    local expectedSignature = tostring(profile and profile.skeletonSignature or "")
    local actualSignature = tostring(stand:GetAttribute("Game1SkeletonSignature") or "")
    if not profile or (expectedSignature ~= "" and actualSignature ~= "" and expectedSignature ~= actualSignature) then
        prompt.Enabled = false
        warn("[game1][character-stand] incompatible or absent animation profile", profileId)
        return function() end
    end
    local clips = Catalog.List(Registry, profileId)
    if #clips == 0 then
        prompt.Enabled = false
        warn("[game1][character-stand] no published animation assets", profileId)
        return function() end
    end
    local host = stand:FindFirstChildOfClass("AnimationController")
    local animator = host and host:FindFirstChildOfClass("Animator")
    if not animator then
        prompt.Enabled = false
        warn("[game1][character-stand] stand has no Animator", profileId)
        return function() end
    end
    local index = 0
    local track: AnimationTrack? = nil
    local currentAnimation: Animation? = nil
    local disposed = false
    local function clearTrack()
        if track then
            track:Stop(0.1)
            track:Destroy()
            track = nil
        end
        if currentAnimation then
            currentAnimation:Destroy()
            currentAnimation = nil
        end
    end
    local connection = prompt.Triggered:Connect(function(_player: Player)
        if disposed or not stand.Parent then return end
        index = index % #clips + 1
        local clip = clips[index]
        clearTrack()
        local animation = Instance.new("Animation")
        animation.Name = clip.clipId
        animation.AnimationId = clip.animationId
        local ok, err = pcall(function()
            local newTrack = (animator :: Animator):LoadAnimation(animation)
            newTrack.Looped = clip.looped
            local priority = Enum.AnimationPriority[clip.priority]
            if priority then newTrack.Priority = priority end
            newTrack:Play(0.1)
            track = newTrack
            currentAnimation = animation
        end)
        if not ok then
            animation:Destroy()
            warn("[game1][character-stand] animation load failed", clip.clipId, err)
        end
        stand:SetAttribute("Game1TestStandCurrentClip", clip.clipId)
        stand:SetAttribute("Game1TestStandClipIndex", index)
        prompt.ActionText = "Следующая анимация (" .. tostring(index) .. "/" .. tostring(#clips) .. ")"
        prompt.ObjectText = profileId .. " · " .. clip.label
        print("[game1][character-stand]", profileId, clip.label, clip.clipId, clip.animationId)
    end)
    return function()
        if disposed then return end
        disposed = true
        connection:Disconnect()
        clearTrack()
    end
end

return table.freeze(Playback)
