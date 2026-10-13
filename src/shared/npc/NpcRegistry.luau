-- generated. do not edit by hand.
return table.freeze({
	schemaVersion = 1,
	project = "game1",
	npcs = table.freeze({
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
		["warsmith"] = table.freeze({
			slug = "warsmith",
			nameEn = "Warsmith",
			nameRu = "Кузнец",
			status = "PUBLISHED",
			modelAssetId = "124938004268790",
			serverStoragePath = "ServerStorage.npcs.warsmith.model.warsmith",
			skeletonSignature = "41228d5fef9590754d49b9a5f3dff78d0fd060c38705980dd9a1092fad91d7f7",
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
				["RunSpeed"] = 200,
				["CritChance"] = 20,
			}),
			textures = table.freeze({
				["warsmith_01_armature_color"] = table.freeze({
					assetId = "82960443952213",
					sha256 = "cd854af79dd67d0bddfd5400e43f734477176c3cd0893fbc9ae3957cdc903041",
				}),
			}),
		}),
	}),
})
