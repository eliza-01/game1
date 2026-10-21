-- generated. do not edit by hand.
return table.freeze({
	schemaVersion = 1,
	project = "game1",
	npcs = table.freeze({
		["warsmith"] = table.freeze({
			slug = "warsmith",
			nameEn = "Warsmith",
			nameRu = "Кузнец",
			status = "PUBLISHED",
			modelAssetId = "94000088091746",
			serverStoragePath = "ServerStorage.npcs.warsmith.model.warsmith",
			skeletonSignature = "f72cbdcfa8c465b044b58822eabafb11531387e0188b62cfd0ca9c34a90ec692",
			behavior = table.freeze({
				retaliateWhenAttacked = true,
				pursuitRadiusStuds = 70,
				returnDelaySeconds = 5,
				attackRadiusStuds = 7,
			}),
			stats = table.freeze({
				["MaxHP"] = 1000,
				["Damage"] = 10,
				["AttackSpeed"] = 200,
				["RunSpeed"] = 110,
				["CritChance"] = 20,
			}),
			textures = table.freeze({
				["warsmith_01_armature_color"] = table.freeze({
					assetId = "82960443952213",
					sha256 = "cd854af79dd67d0bddfd5400e43f734477176c3cd0893fbc9ae3957cdc903041",
				}),
			}),
		}),
		["guard_01"] = table.freeze({
			slug = "guard_01",
			nameEn = "Guard 01",
			nameRu = "Гвард 01",
			status = "PUBLISHED",
			modelAssetId = "102352964220583",
			serverStoragePath = "ServerStorage.npcs.guard_01.model.guard_01",
			skeletonSignature = "cd30e10f85635d9532b6223beeb86086030f09fe8d19daab9cc3c6b6f4cf8922",
			behavior = table.freeze({
				retaliateWhenAttacked = true,
				pursuitRadiusStuds = 150,
				returnDelaySeconds = 5,
				attackRadiusStuds = 7,
			}),
			stats = table.freeze({
				["MaxHP"] = 3000,
				["Damage"] = 2,
				["AttackSpeed"] = 300,
				["RunSpeed"] = 150,
				["CritChance"] = 20,
			}),
			textures = table.freeze({
				["helmet_guard_armature_color"] = table.freeze({
					assetId = "138600883246534",
					sha256 = "2d33b2d7e1ae367aa858938a1b5a8acb31844d2191bc035e70a17dba09a51cf6",
				}),
			}),
		}),
	}),
})
