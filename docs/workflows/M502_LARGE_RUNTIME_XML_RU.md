# M502 · Large Runtime XML Places

M501 still imposed a fixed 150 MiB limit in the local Runtime compiler, including its verification of the generated XML. M502 removes that limit entirely for both the source and compiled Place. The source must still be a regular nonempty valid Roblox XML file; freshness checks, SHA256, backup, geometry/referent checks and the closed publish gate remain unchanged.

The existing ElementTree compiler loads the XML into RAM and can hold two trees during output verification. This change does not make memory or disk usage constant, and does not change Roblox platform limits. An actual Python MemoryError during parsing is reported explicitly. Save current authoring XML to the existing path, Scan Place, Preflight and prepare the Runtime as before.

Regression uses a synthetic XML with 151 MiB of preserved property payload, runs Preflight, backup, compile and reopen, checks backup hash and preserved payload hashes. Studio acceptance of the real large Place is separate.
