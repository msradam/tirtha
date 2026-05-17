"""Build the 10-country showcase dataset.

Runs `tirtha accessibility run` for each country at 100m resolution and
saves outputs to docs/cases/{iso3}/. The marimo showcase notebook
(notebooks/03_showcase.py) reads these.

Picks span sub-Saharan Africa, South Asia, conflict zones, and
mountainous terrain. All LMIC so the WorldPop maxar_v1 product is
available.

Run:
    uv run python scripts/build_country_cases.py

About 5-10 minutes per country, 60-90 minutes total. Skips any country
whose output directory already exists. Use --force to rebuild.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from tirtha.io import write_outputs
from tirtha.pipeline import run_accessibility
from tirtha.viz import save_headline_figure


COUNTRIES = [
    # iso3, geocode_name, resolution_m, blurb
    ("SLE", "Sierra Leone",         100, "Post-Ebola West Africa, the audit's flagship test case."),
    ("MWI", "Malawi",               100, "Long-running MAP comparator. Blantyre is the original chip."),
    ("BFA", "Burkina Faso",         100, "Sahel terrain, conflict-affected, audit's alt v1 target."),
    ("LBR", "Liberia",              100, "Small West African, post-war health-system rebuild."),
    ("RWA", "Rwanda",               100, "Post-conflict, well-mapped, mountainous."),
    ("MDG", "Madagascar",           100, "Island, rural-heavy, dispersed infrastructure."),
    ("NPL", "Nepal",                100, "Steep terrain. Tobler slope penalty actually bites here."),
    ("HTI", "Haiti",                100, "Post-2010 earthquake, dense urban-rural mix."),
    ("ETH", "Ethiopia",             100, "Large LMIC, varied terrain, multiple ADM1 contrasts."),
    ("BGD", "Bangladesh",           100, "Dense, low-elevation, Cox's Bazar refugee context."),
]


def build_one(iso3: str, region: str, resolution_m: int, blurb: str, out_root: Path, force: bool) -> dict | None:
    """Run the pipeline for one country and write outputs."""
    out_dir = out_root / iso3.lower()
    if out_dir.exists() and not force:
        existing = out_dir / "metrics.json"
        if existing.exists():
            print(f"  [{iso3}] cached, skipping")
            return json.loads(existing.read_text())
        print(f"  [{iso3}] partial cache, removing and rebuilding")
        shutil.rmtree(out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    print(f"  [{iso3}] {region} @ {resolution_m}m ...")
    try:
        result = run_accessibility(
            region=region,
            resolution_m=resolution_m,
            verbose=True,
        )
    except Exception as exc:
        print(f"  [{iso3}] FAILED: {type(exc).__name__}: {exc}")
        (out_dir / "failed.txt").write_text(f"{type(exc).__name__}: {exc}\n")
        return None

    write_outputs(result, out_dir)
    save_headline_figure(result, out_dir / "figures" / "headline.png", title=region)

    case_info = {
        "iso3": iso3,
        "region": region,
        "resolution_m": resolution_m,
        "blurb": blurb,
        "elapsed_s": round(time.time() - t0, 1),
        "accessibility": result.accessibility.as_dict(),
        "n_destinations": result.n_destinations,
        "bbox_wsen": list(result.bbox_wsen),
        "crs": result.crs,
    }
    (out_dir / "case.json").write_text(json.dumps(case_info, indent=2))
    print(f"  [{iso3}] done in {case_info['elapsed_s']:.0f}s")
    return case_info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="rebuild even if cached")
    parser.add_argument("--only", nargs="+", default=None, help="iso3 codes to build (default all)")
    parser.add_argument("--out", type=Path, default=Path("docs/cases"))
    args = parser.parse_args()

    out_root = args.out
    out_root.mkdir(parents=True, exist_ok=True)

    selected = COUNTRIES
    if args.only:
        wanted = {c.upper() for c in args.only}
        selected = [c for c in COUNTRIES if c[0] in wanted]

    print(f"Building {len(selected)} country case(s) at out={out_root}")
    summaries = []
    overall_t0 = time.time()
    for iso3, region, res, blurb in selected:
        info = build_one(iso3, region, res, blurb, out_root, args.force)
        if info is not None:
            summaries.append(info)

    # Aggregate index for the showcase notebook to read.
    (out_root / "index.json").write_text(json.dumps(
        {"cases": summaries, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
        indent=2,
    ))
    elapsed = time.time() - overall_t0
    print(f"\nAll done. {len(summaries)}/{len(selected)} succeeded in {elapsed/60:.1f} min.")
    return 0 if len(summaries) == len(selected) else 1


if __name__ == "__main__":
    sys.exit(main())
