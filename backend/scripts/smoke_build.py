"""Offline smoke test: build a tiny SWMM model.inp with no live data and no external APIs.

Clone the repo, install the backend, then run this to confirm the core build pipeline works
before touching any geospatial data or the network — so a fresh user isn't blocked on the
geospatial environment or an external portal being slow/down:

    backend/.venv/bin/python backend/scripts/smoke_build.py

It assembles a hand-made 2-junction network + 1 subcatchment + a 3-hour rain series into a
model.inp, round-tripped through the SWMM writer (swmm-api + swmmio) so a successful run
proves the install is sound. With EPA SWMM (`swmm5`) on PATH it also runs the engine and
reports continuity; without it, building + round-tripping the .inp is the offline check.
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

from swmmcanada.build import (
    BuildConfig,
    ConduitIn,
    JunctionIn,
    NetworkIn,
    OutfallIn,
    RainfallSeries,
    SubcatchmentIn,
    build_model,
)


def build_tiny(out_dir: Path):
    network = NetworkIn(
        junctions=[
            JunctionIn("J1", invert_m=99.0, x=0.0, y=0.0),
            JunctionIn("J2", invert_m=98.5, x=100.0, y=0.0),
        ],
        outfalls=[OutfallIn("O1", invert_m=98.0, x=200.0, y=0.0)],
        conduits=[
            ConduitIn("C1", "J1", "J2", length_m=100.0),
            ConduitIn("C2", "J2", "O1", length_m=100.0),
        ],
    )
    subs = [
        SubcatchmentIn("S1", outlet_node="J1", area_ha=1.0, pct_imperv=40.0, width_m=100.0, pct_slope=1.0)
    ]
    rain = RainfallSeries(
        timestamps=[datetime(2020, 6, 1, h) for h in range(3)],
        precip_mm=[1.2, 3.4, 0.0],
    )
    cfg = BuildConfig(out_dir=out_dir, start=date(2020, 6, 1), end=date(2020, 6, 2))
    return build_model(network=network, subcatchments=subs, rain=rain, config=cfg)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", help="output dir (default: a fresh temp dir)")
    args = ap.parse_args()

    out_dir = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="swmmcanada_smoke_"))
    out_dir.mkdir(parents=True, exist_ok=True)

    res = build_tiny(out_dir)
    if not res.inp_path.exists():
        sys.exit("FAIL: build did not write model.inp")
    print(f"OK   built + round-tripped {res.inp_path}")
    print(f"     sections: {', '.join(res.sections_written)}")

    swmm5 = shutil.which("swmm5")
    if swmm5:
        rpt = res.inp_path.with_suffix(".rpt")
        proc = subprocess.run(
            [swmm5, str(res.inp_path), str(rpt), str(res.inp_path.with_suffix(".out"))],
            capture_output=True, text=True,
        )
        if proc.returncode == 0:
            print(f"OK   EPA SWMM engine ran clean -> {rpt}")
        else:
            print("WARN EPA SWMM engine returned non-zero:\n" + proc.stdout + proc.stderr)
    else:
        print("note: EPA SWMM (`swmm5`) not on PATH — skipped the engine run "
              "(building + round-tripping the .inp is the offline check).")

    print(f"\nSmoke test passed. Output in {out_dir}")


if __name__ == "__main__":
    main()
