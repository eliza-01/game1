-- generated. do not edit by hand.
return table.freeze({
	schemaVersion = 2,
	project = "game1",
	profiles = table.freeze({
		["human_female"] = table.freeze({
			skeletonSignature = "6b825a0cd2cdeaf700fca3c853fb52d41e9f170020b012d7d1188d4f9352210c",
			base = table.freeze({
				["death"] = table.freeze({
					table.freeze({
						clipId = "human_female__base__death__00",
						assetId = "81644864777234",
						animationId = "rbxassetid://81644864777234",
						variant = 0,
						weight = 100,
						looped = false,
						priority = "Action",
						document = nil,
					}),
				}),
				["revive"] = table.freeze({
					table.freeze({
						clipId = "human_female__base__revive__00",
						assetId = "83724299950111",
						animationId = "rbxassetid://83724299950111",
						variant = 0,
						weight = 100,
						looped = false,
						priority = "Action",
						document = nil,
					}),
				}),
			}),
			emotions = table.freeze({
			}),
			weapons = table.freeze({
				["1hs"] = table.freeze({
					["attack"] = table.freeze({
						table.freeze({
							clipId = "human_female__weapon__1hs__attack__01",
							assetId = "122840035798169",
							animationId = "rbxassetid://122840035798169",
							variant = 1,
							weight = 100,
							looped = false,
							priority = "Action",
							document = nil,
						}),
						table.freeze({
							clipId = "human_female__weapon__1hs__attack__02",
							assetId = "111523407571664",
							animationId = "rbxassetid://111523407571664",
							variant = 2,
							weight = 100,
							looped = false,
							priority = "Action",
							document = nil,
						}),
						table.freeze({
							clipId = "human_female__weapon__1hs__attack__03",
							assetId = "132390395868663",
							animationId = "rbxassetid://132390395868663",
							variant = 3,
							weight = 100,
							looped = false,
							priority = "Action",
							document = nil,
						}),
					}),
					["combat_idle"] = table.freeze({
						table.freeze({
							clipId = "human_female__weapon__1hs__combat_idle__00",
							assetId = "78672231936532",
							animationId = "rbxassetid://78672231936532",
							variant = 0,
							weight = 100,
							looped = true,
							priority = "Idle",
							document = nil,
						}),
					}),
					["idle"] = table.freeze({
						table.freeze({
							clipId = "human_female__weapon__1hs__idle__00",
							assetId = "104882544264186",
							animationId = "rbxassetid://104882544264186",
							variant = 0,
							weight = 100,
							looped = true,
							priority = "Idle",
							document = nil,
						}),
					}),
					["run"] = table.freeze({
						table.freeze({
							clipId = "human_female__weapon__1hs__run__00",
							assetId = "70447016661017",
							animationId = "rbxassetid://70447016661017",
							variant = 0,
							weight = 100,
							looped = true,
							priority = "Movement",
							document = nil,
						}),
					}),
					["walk"] = table.freeze({
						table.freeze({
							clipId = "human_female__weapon__1hs__walk__00",
							assetId = "82213044013946",
							animationId = "rbxassetid://82213044013946",
							variant = 0,
							weight = 100,
							looped = true,
							priority = "Movement",
							document = nil,
						}),
					}),
				}),
			}),
		}),
		["human_male"] = table.freeze({
			skeletonSignature = "81519687bd1413ddf34287374fa5ef61f46c52d3976c5be95aa06e5204f56496",
			base = table.freeze({
			}),
			emotions = table.freeze({
				["blink"] = table.freeze({
					table.freeze({
						clipId = "human_male__emotions__blink__00",
						assetId = "",
						animationId = "",
						variant = 0,
						weight = 100,
						looped = false,
						priority = "Action2",
						document = {["schema_version"]=1,["clip_name"]="emotions_blink",["source_action"]="face_blink",["fps"]=30.0,["frame_start"]=1,["frame_end"]=90,["looped"]=false,["mode"]="procedural",["events"]={{["id"]="event_0001",["frame"]=1,["time"]=0.0,["name"]="face_state",["parameters"]={["name"]="blink"}},{["id"]="event_0002",["frame"]=1,["time"]=0.0,["name"]="blink",["parameters"]={["duration"]=0.2}},{["id"]="event_0003",["frame"]=90,["time"]=2.966666666666667,["name"]="face_reset",["parameters"]={}}},["duration"]=2.966666666666667},
					}),
				}),
				["closed"] = table.freeze({
					table.freeze({
						clipId = "human_male__emotions__closed__00",
						assetId = "",
						animationId = "",
						variant = 0,
						weight = 100,
						looped = true,
						priority = "Action2",
						document = {["schema_version"]=1,["clip_name"]="emotions_closed",["source_action"]="face_closed",["fps"]=30.0,["frame_start"]=1,["frame_end"]=90,["looped"]=true,["mode"]="procedural",["events"]={{["id"]="event_0001",["frame"]=1,["time"]=0.0,["name"]="face_state",["parameters"]={["name"]="closed"}}},["duration"]=2.966666666666667},
					}),
				}),
				["dizzy_spiral"] = table.freeze({
					table.freeze({
						clipId = "human_male__emotions__dizzy_spiral__00",
						assetId = "",
						animationId = "",
						variant = 0,
						weight = 100,
						looped = false,
						priority = "Action2",
						document = {["schema_version"]=1,["clip_name"]="emotions_dizzy_spiral",["source_action"]="face_wait_special_dizzy_spiral_smooth",["fps"]=30.0,["frame_start"]=1,["frame_end"]=160,["looped"]=false,["mode"]="procedural",["events"]={{["id"]="event_0001",["frame"]=1,["time"]=0.0,["name"]="face_state",["parameters"]={["name"]="dizzy_spiral"}},{["id"]="event_0002",["frame"]=10,["time"]=0.3,["name"]="eyes_set",["parameters"]={["name"]="spiral"}},{["id"]="event_0003",["frame"]=10,["time"]=0.3,["name"]="eyes_spin_start",["parameters"]={["degrees_per_second"]=180}},{["id"]="event_0004",["frame"]=140,["time"]=4.633333333333334,["name"]="eyes_spin_stop",["parameters"]={}},{["id"]="event_0005",["frame"]=140,["time"]=4.633333333333334,["name"]="eyes_set",["parameters"]={["name"]="normal"}},{["id"]="event_0006",["frame"]=140,["time"]=4.633333333333334,["name"]="face_reset",["parameters"]={}},{["id"]="event_0007",["frame"]=160,["time"]=5.3,["name"]="face_reset",["parameters"]={}}},["duration"]=5.3},
					}),
				}),
				["happy"] = table.freeze({
					table.freeze({
						clipId = "human_male__emotions__happy__00",
						assetId = "",
						animationId = "",
						variant = 0,
						weight = 100,
						looped = true,
						priority = "Action2",
						document = {["schema_version"]=1,["clip_name"]="emotions_happy",["source_action"]="face_happy",["fps"]=30.0,["frame_start"]=1,["frame_end"]=90,["looped"]=true,["mode"]="procedural",["events"]={{["id"]="event_0001",["frame"]=1,["time"]=0.0,["name"]="face_state",["parameters"]={["name"]="happy"}}},["duration"]=2.966666666666667},
					}),
				}),
				["happy_sharp_caret"] = table.freeze({
					table.freeze({
						clipId = "human_male__emotions__happy_sharp_caret__00",
						assetId = "",
						animationId = "",
						variant = 0,
						weight = 100,
						looped = true,
						priority = "Action2",
						document = {["schema_version"]=1,["clip_name"]="emotions_happy_sharp_caret",["source_action"]="face_happy_sharp_caret",["fps"]=30.0,["frame_start"]=1,["frame_end"]=90,["looped"]=true,["mode"]="procedural",["events"]={{["id"]="event_0001",["frame"]=1,["time"]=0.0,["name"]="face_state",["parameters"]={["name"]="happy_sharp_caret"}}},["duration"]=2.966666666666667},
					}),
				}),
				["happy_thick_caret"] = table.freeze({
					table.freeze({
						clipId = "human_male__emotions__happy_thick_caret__00",
						assetId = "",
						animationId = "",
						variant = 0,
						weight = 100,
						looped = true,
						priority = "Action2",
						document = {["schema_version"]=1,["clip_name"]="emotions_happy_thick_caret",["source_action"]="face_happy_thick_caret",["fps"]=30.0,["frame_start"]=1,["frame_end"]=90,["looped"]=true,["mode"]="procedural",["events"]={{["id"]="event_0001",["frame"]=1,["time"]=0.0,["name"]="face_state",["parameters"]={["name"]="happy_thick_caret"}}},["duration"]=2.966666666666667},
					}),
				}),
				["indignant_surprise"] = table.freeze({
					table.freeze({
						clipId = "human_male__emotions__indignant_surprise__00",
						assetId = "",
						animationId = "",
						variant = 0,
						weight = 100,
						looped = false,
						priority = "Action2",
						document = {["schema_version"]=1,["clip_name"]="emotions_indignant_surprise",["source_action"]="face_indignant_surprise",["fps"]=30.0,["frame_start"]=1,["frame_end"]=90,["looped"]=false,["mode"]="procedural",["events"]={{["id"]="event_0001",["frame"]=1,["time"]=0.0,["name"]="face_state",["parameters"]={["name"]="indignant_surprise"}},{["id"]="event_0002",["frame"]=90,["time"]=2.966666666666667,["name"]="face_reset",["parameters"]={}}},["duration"]=2.966666666666667},
					}),
				}),
				["nausea_wave"] = table.freeze({
					table.freeze({
						clipId = "human_male__emotions__nausea_wave__00",
						assetId = "",
						animationId = "",
						variant = 0,
						weight = 100,
						looped = false,
						priority = "Action2",
						document = {["schema_version"]=1,["clip_name"]="emotions_nausea_wave",["source_action"]="face_wait_special_nausea_wave",["fps"]=30.0,["frame_start"]=1,["frame_end"]=160,["looped"]=false,["mode"]="procedural",["events"]={{["id"]="event_0001",["frame"]=1,["time"]=0.0,["name"]="face_state",["parameters"]={["name"]="nausea_wave"}},{["id"]="event_0002",["frame"]=160,["time"]=5.3,["name"]="face_reset",["parameters"]={}}},["duration"]=5.3},
					}),
				}),
			}),
			weapons = table.freeze({
			}),
		}),
	}),
})
