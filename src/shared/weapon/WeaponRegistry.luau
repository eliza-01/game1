-- generated. do not edit by hand.
return table.freeze({
	schemaVersion = 1,
	project = "game1",
	activeWeaponSlug = "",
	weapons = table.freeze({
		["newbie_axe"] = table.freeze({
			slug = "newbie_axe",
			nameEn = "Newbie Axe",
			nameRu = "Топор Новичка",
			weaponType = "1hs",
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
			weaponType = "1hs",
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
