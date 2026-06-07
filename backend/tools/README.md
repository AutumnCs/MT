# Tools

Utilities for maintenance, validation, and data synchronization.

## `amap_poi_sync.py`

Synchronizes local POI records with GaoDe Web API facts.

Typical usage:

```powershell
cd backend
python tools\amap_poi_sync.py --input pois.json --output pois.amap.json
```

If no GaoDe key is configured, the tool runs in dry-run mode and prints a validation
report without calling the network.

## `generate_mock_ugc.py`

Generates development-only mixed UGC fields for local POIs. The script is
deterministic by default and writes both positive and negative review signals,
so the data does not become unrealistically perfect.

Typical usage:

```powershell
cd backend
python tools\generate_mock_ugc.py --input pois.json --output pois.with_ugc.json
```

After checking the output, either copy the useful fields back into `pois.json`
or run with `--in-place`:

```powershell
python tools\generate_mock_ugc.py --input pois.json --in-place
```

Generated fields include:

- `review_keywords`
- `positive_reviews`
- `neutral_reviews`
- `negative_reviews`
- `review_signals`
- `ugc_summary`

`review_signals` is consumed by `backend/services/review_analyzer.py` before
falling back to keyword analysis and hand-written score fields.

## `expand_local_pois.py`

Appends curated local demo POIs without calling GaoDe or any external service.
This is useful when the project needs more route diversity before map-provider
fact checking is enabled.

Typical usage:

```powershell
cd backend
python tools\expand_local_pois.py --input pois.json --output pois.json
python tools\enrich_area_clusters.py --input pois.json --output pois.json
python tools\generate_mock_ugc.py --input pois.json --in-place
```

The script merges by `id`, so rerunning it updates the same demo records instead
of duplicating them.

## `enrich_area_clusters.py`

Adds local route-planning area hints such as `area_cluster`, `area_label`, and
`business_area`. These fields help route planning prefer POIs in the same
compact city area before a real map provider is connected.

Typical usage:

```powershell
cd backend
python tools\enrich_area_clusters.py --input pois.json --output pois.json
```

Current local demo scale after running the expansion script:

- 153 POIs total
- Guangzhou: 73 POIs
- Shanghai: 80 POIs
- Category coverage: food, coffee, street, shopping, museum, exhibition, night,
  park, scene, and library
- Area clusters: Guangzhou old town / Dongshankou / Zhujiang New Town /
  Haizhu Tower / Tianhe, Shanghai Bund / Jing'an / Xuhui / North Bund /
  Pudong / Yangpu / Changning
- Mixed UGC after regeneration: positive comments remain the majority, with
  neutral and negative feedback retained for realistic ranking signals

