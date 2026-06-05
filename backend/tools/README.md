# Tools

Utilities for maintenance, validation, and data synchronization.

## `amap_poi_sync.py`

Synchronizes local POI records with GaoDe Web API facts.

Typical usage:

```powershell
cd G:\MeituanAgent\backend
python tools\amap_poi_sync.py --input pois.json --output pois.amap.json
```

If no GaoDe key is configured, the tool runs in dry-run mode and prints a validation
report without calling the network.

