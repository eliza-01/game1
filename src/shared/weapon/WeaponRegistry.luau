-- generated. do not edit by hand.
return table.freeze({
	schemaVersion = 2,
	project = "game1",
	activeWeaponSlug = "newbie_sword_01",
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
		["newbie_dagger"] = table.freeze({
			slug = "newbie_dagger",
			nameEn = "Newbie Dagger",
			nameRu = "Кинжал Новичка",
			weaponType = "dagger",
			rarity = "common",
			attackRadiusStuds = 3,
			status = "PUBLISHED",
			modelAssetId = "93764003011141",
			serverStoragePath = "ServerStorage.weapons.dagger.newbie_dagger.model.newbie_dagger",
			statModifiers = table.freeze({
				["AttackSpeed"] = 0,
				["Damage"] = 0,
			}),
			textures = table.freeze({
				["newbie_dagger_01"] = table.freeze({
					assetId = "93664090329756",
					sha256 = "33acf7c94a464b263a936c0e8acb4d03bd891eeddd803b2976c6d2eafb1270b2",
				}),
			}),
		}),
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
		["newbie_sword_01"] = table.freeze({
			slug = "newbie_sword_01",
			nameEn = "Newbie Sword 01",
			nameRu = "Меч Новичка 01",
			weaponType = "sword",
			rarity = "common",
			attackRadiusStuds = 4,
			status = "PUBLISHED",
			modelAssetId = "89658066107896",
			serverStoragePath = "ServerStorage.weapons.sword.newbie_sword_01.model.newbie_sword_01",
			statModifiers = table.freeze({
				["AttackSpeed"] = 0,
				["Damage"] = 0,
			}),
			textures = table.freeze({
				["newbie_sword_01"] = table.freeze({
					assetId = "127316574053686",
					sha256 = "2ad6323ed05598ff5d88a1ffadb904e867f99eeaf7e2751557e8b349657626f1",
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
		["guards_sword_01"] = table.freeze({
			slug = "guards_sword_01",
			nameEn = "Guards Sword 01",
			nameRu = "Меч Гварда 01",
			weaponType = "sword",
			rarity = "uncommon",
			attackRadiusStuds = 7,
			status = "PUBLISHED",
			modelAssetId = "131917076297036",
			serverStoragePath = "ServerStorage.weapons.sword.guards_sword_01.model.guards_sword_01",
			statModifiers = table.freeze({
				["AttackSpeed"] = 0,
				["Damage"] = 0,
			}),
			textures = table.freeze({
				["guards_sword_01"] = table.freeze({
					assetId = "75862292451032",
					sha256 = "3f6c0de95bbabc907c0573bb18d238cb629f333cd7daa7a67a54014adb63cc26",
				}),
			}),
		}),
		["warsmiths_hummer_01"] = table.freeze({
			slug = "warsmiths_hummer_01",
			nameEn = "Warsmiths Hummer 01",
			nameRu = "Молот Кузнеца 01",
			weaponType = "sword",
			rarity = "uncommon",
			attackRadiusStuds = 7,
			status = "PUBLISHED",
			modelAssetId = "136542486506010",
			serverStoragePath = "ServerStorage.weapons.sword.warsmiths_hummer_01.model.warsmiths_hummer_01",
			statModifiers = table.freeze({
				["AttackSpeed"] = 0,
				["Damage"] = 0,
			}),
			textures = table.freeze({
				["warsmiths_hummer"] = table.freeze({
					assetId = "73070479826352",
					sha256 = "3f6c0de95bbabc907c0573bb18d238cb629f333cd7daa7a67a54014adb63cc26",
				}),
			}),
		}),
	}),
})
