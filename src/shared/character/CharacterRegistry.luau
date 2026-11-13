-- generated. do not edit by hand.
return table.freeze({
	schemaVersion = 5,
	project = "game1",
	activeArchetypeId = "human_female",
	defaultArchetypeId = "human_female",
	studioAdminArchetypeId = "human_female",
	archetypes = {
		table.freeze({
			id = "human_female",
			displayName = "Human Female",
			race = "human",
			gender = "female",
			status = "ASSEMBLY_READY",
			visualMode = "assembly",
			revision = 14,
			stats = table.freeze({
				Level = 2,
				MaxHP = 100,
				Damage = 10,
				Defense = 0,
				AttackSpeed = 177,
				RunSpeed = 155,
				CritChance = 0,
			}),
			model = table.freeze({
				assetId = nil,
				sourcePath = "",
				sha256 = "",
			}),
			skeleton = table.freeze({
				armature = "human_female_armature",
				boneCount = 77,
				meshCount = 10,
				signature = "1f420b74eeeb7d27fdf2f0b48207a9a4363a17ad622b339d0c7abee30dfc6265",
			}),
			assembly = {["schema_version"]=2,["rig"]={["id"]="human_female",["asset_id"]="101730982429113",["revision"]=2,["bone_names"]={"back_mount","cape_clasp_l","cape_clasp_r","cape_mount","clavicle_l","clavicle_r","face_brow_l","face_brow_r","face_eye_l","face_eye_r","face_head","face_mouth","face_mustache","foot_l","foot_r","forearm_l","forearm_r","hair_mount","hand_l","hand_r","head","index_01_l","index_01_r","index_02_l","index_02_r","index_03_l","index_03_r","middle_01_l","middle_01_r","middle_02_l","middle_02_r","middle_03_l","middle_03_r","neck","palm_01_l","palm_01_r","palm_02_l","palm_02_r","palm_03_l","palm_03_r","palm_04_l","palm_04_r","palm_05_l","palm_05_r","pelvis","pinky_01_l","pinky_01_r","pinky_02_l","pinky_02_r","pinky_03_l","pinky_03_r","ring_01_l","ring_01_r","ring_02_l","ring_02_r","ring_03_l","ring_03_r","shield_mount_l","shin_l","shin_r","shoulder_mount_l","shoulder_mount_r","spine_01","spine_02","spine_03","thigh_l","thigh_r","thumb_01_l","thumb_01_r","thumb_02_l","thumb_02_r","toe_l","toe_r","upper_arm_l","upper_arm_r","weapon_grip_l","weapon_grip_r"}},["parts"]={["boots"]={["id"]="human_common_m001_boots",["asset_id"]="89751778683119",["revision"]=1,["mesh_family_id"]="human_common_m001",["appearance_id"]="atlas_76",["used_bones"]={"foot_l","foot_r","shin_l","shin_r","toe_l","toe_r"},["attachment"]="",["attachment_mode"]="",["socket_bone"]="pelvis",["extras"]={},["atlas_image_id"]="80567785049994"},["gloves"]={["id"]="human_common_m001_gloves",["asset_id"]="127410733314519",["revision"]=1,["mesh_family_id"]="human_common_m001",["appearance_id"]="atlas_13",["used_bones"]={"forearm_l","forearm_r","hand_l","hand_r","index_01_l","index_01_r","index_02_l","index_02_r","index_03_l","index_03_r","middle_01_l","middle_01_r","middle_02_l","middle_02_r","middle_03_l","middle_03_r","palm_01_l","palm_01_r","palm_02_l","palm_02_r","palm_03_l","palm_03_r","palm_04_l","palm_04_r","palm_05_l","palm_05_r","pinky_01_l","pinky_01_r","pinky_02_l","pinky_02_r","pinky_03_l","pinky_03_r","ring_01_l","ring_01_r","ring_02_l","ring_02_r","ring_03_l","ring_03_r","thumb_01_l","thumb_01_r","thumb_02_l","thumb_02_r","upper_arm_l","upper_arm_r"},["attachment"]="",["attachment_mode"]="",["socket_bone"]="pelvis",["extras"]={},["atlas_image_id"]="135524533752769"},["lower"]={["id"]="human_female_m001_lower",["asset_id"]="116052017559063",["revision"]=1,["mesh_family_id"]="human_female_m001",["appearance_id"]="atlas_79",["used_bones"]={"pelvis","shin_l","shin_r","spine_01","thigh_l","thigh_r"},["attachment"]="",["attachment_mode"]="",["socket_bone"]="pelvis",["extras"]={},["atlas_image_id"]="132223474608791"},["upper"]={["id"]="human_female_m001_upper",["asset_id"]="90300066845686",["revision"]=1,["mesh_family_id"]="human_female_m001",["appearance_id"]="atlas_80",["used_bones"]={"clavicle_l","clavicle_r","forearm_l","forearm_r","head","neck","pelvis","spine_01","spine_02","spine_03","upper_arm_l","upper_arm_r"},["attachment"]="",["attachment_mode"]="",["socket_bone"]="pelvis",["extras"]={},["atlas_image_id"]="96797400877623"},["head"]={["id"]="human_female_m001_head",["asset_id"]="120680843372006",["revision"]=1,["mesh_family_id"]="human_female_m001",["appearance_id"]="atlas_78",["used_bones"]={"head","neck"},["attachment"]="",["attachment_mode"]="",["socket_bone"]="pelvis",["extras"]={},["atlas_image_id"]="85225816215207"},["eye_l"]={["id"]="human_common_m001_eye_l",["asset_id"]="109477519119435",["revision"]=1,["mesh_family_id"]="human_common_m001",["appearance_id"]="",["used_bones"]={"face_eye_l"},["attachment"]="",["attachment_mode"]="",["socket_bone"]="pelvis",["extras"]={},["atlas_image_id"]="",["color"]="#9EDFFF",["material"]="Metal"},["eye_r"]={["id"]="human_common_m001_eye_r",["asset_id"]="77502187653505",["revision"]=1,["mesh_family_id"]="human_common_m001",["appearance_id"]="",["used_bones"]={"face_eye_r"},["attachment"]="",["attachment_mode"]="",["socket_bone"]="pelvis",["extras"]={},["atlas_image_id"]="",["color"]="#FFBDF3",["material"]="Metal"},["eyebrow_l"]={["id"]="human_common_m001_eyebrow_l",["asset_id"]="96041697638875",["revision"]=1,["mesh_family_id"]="human_common_m001",["appearance_id"]="",["used_bones"]={"face_brow_l"},["attachment"]="",["attachment_mode"]="",["socket_bone"]="pelvis",["extras"]={},["atlas_image_id"]="",["color"]="#000000"},["eyebrow_r"]={["id"]="human_common_m001_eyebrow_r",["asset_id"]="88353012521312",["revision"]=1,["mesh_family_id"]="human_common_m001",["appearance_id"]="",["used_bones"]={"face_brow_r"},["attachment"]="",["attachment_mode"]="",["socket_bone"]="pelvis",["extras"]={},["atlas_image_id"]="",["color"]="#000000"},["hair"]={["id"]="human_female_m001_hair",["asset_id"]="93538100175421",["revision"]=1,["mesh_family_id"]="human_female_m001",["appearance_id"]="",["used_bones"]={},["attachment"]="hair_mount",["attachment_mode"]="pivot",["socket_bone"]="",["extras"]={},["atlas_image_id"]="",["colors"]={["primary"]="#FFB8D1"},["material"]="Plaster"}},["ready"]=true,["missing"]={},["fingerprint"]="6a34c19d3f539fd32d886a89"},
		}),
	},
})
