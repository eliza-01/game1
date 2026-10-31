--!strict
local names = {}
for _, name in {"idle", "combat_idle", "happy", "happy_sharp_caret", "happy_thick_caret", "sad", "blink",
    "closed", "indignant_surprise", "dizzy_spiral", "look_around", "nausea_wave", "raised_eyebrow"} do
    names[name] = true
end
return table.freeze({attribute = "FaceEmotion", names = table.freeze(names),
    controls = table.freeze({"face_eye_l", "face_eye_r", "face_brow_l", "face_brow_r"})})
