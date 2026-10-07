-- generated. do not edit by hand.
return table.freeze({
	schemaVersion = 2,
	project = "game1",
	activeWeaponSlug = "",
	attackMovementByType = table.freeze({
		["dagger"] = table.freeze({
			animationSet = "1hs",
			locomotionMode = "Run",
			runSpeedMultiplier = 1,
		}),
		["sword"] = table.freeze({
			animationSet = "1hs",
			locomotionMode = "Run",
			runSpeedMultiplier = 1,
		}),
		["bigsword"] = table.freeze({
			animationSet = "2hs",
			locomotionMode = "Walk",
			runSpeedMultiplier = 0.75,
		}),
		["bow"] = table.freeze({
			animationSet = "bow",
			locomotionMode = "Walk",
			runSpeedMultiplier = 0.75,
		}),
	}),
	weapons = table.freeze({
		["newbie_axe"] = table.freeze({
			slug = "newbie_axe",
			nameEn = "Newbie Axe",
			nameRu = "Топор Новичка",
			weaponType = "sword",
			rarity = "common",
			attackRadiusStuds = 7,
			status = "PUBLISHED",
			modelAssetId = "98087242454283",
			serverStoragePath = "ServerStorage.weapons.1hs.newbie_axe.model.newbie_axe",
			statModifiers = table.freeze({
				["AttackSpeed"] = 50,
				["Damage"] = 10,
			}),
			textures = table.freeze({
				["starter_axe_01"] = table.freeze({
					assetId = "114414624522732",
					sha256 = "697f198b97b642a92552dd6da2525250e01a55ee445461bd2016734e6cc8f7dd",
				}),
			}),
		}),
		["dragon_divider"] = table.freeze({
			slug = "dragon_divider",
			nameEn = "Dragon Divider",
			nameRu = "Рассекатель Драконов",
			weaponType = "sword",
			rarity = "legendary",
			attackRadiusStuds = 7,
			status = "PUBLISHED",
			modelAssetId = "104973757039880",
			serverStoragePath = "ServerStorage.weapons.1hs.dragon_divider.model.dragon_divider",
			statModifiers = table.freeze({
				["AttackSpeed"] = 100,
				["Damage"] = 50,
			}),
			textures = table.freeze({
			}),
		}),
	}),
})
