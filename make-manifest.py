#!/usr/bin/env python
"""Generate a manifest CSV file for a set of Quip features. This depends on the
directory made by `convert-json-to-quip.py`."""

import argparse
from pathlib import Path
import sys

import pandas as pd


def get_parsed_args(args=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", help="Path to top-level directory of Quip things.")
    p.add_argument("output", help="Path to output CSV")
    p.add_argument(
        "--tcga-manifest",
        required=True,
        help="Path to TCGA manifest file from Quip",
    )
    args = p.parse_args(args)
    args.input = Path(args.input)
    if not args.input.exists():
        p.error(f"input not found: {args.input}")
    args.output = Path(args.output)
    args.tcga_manifest = Path(args.tcga_manifest)
    if not args.tcga_manifest.exists():
        p.error(f"tcga manifest file not found: {args.tcga_manifest}")
    return args


def main(args=None):
    args = get_parsed_args(args)
    paad_manifest = pd.read_csv(args.tcga_manifest)
    # Set index to {subjectid}-{case-id}
    paad_manifest = paad_manifest.set_index(
        paad_manifest.loc[:, "clinicaltrialsubjectid"]
        + "-"
        + paad_manifest.loc[:, "imageid"]
    )

    # All of these are unique, because they are directory names.
    all_subjid_caseid = [p.name for p in args.input.glob("*") if p.is_dir()]
    print(f"Found {len(all_subjid_caseid)} subject-case pairs")
    rows = []
    for subjid_caseid in all_subjid_caseid:
        print(f"Working on {subjid_caseid} ...")
        paths_for_this_sample = (args.input / subjid_caseid).glob("*")

        try:
            paad_row = paad_manifest.loc[subjid_caseid]
        except KeyError:
            print(f"[WARNING] manifest does not contain {subjid_caseid}")
            print("[WARNING] skipping...")
            continue
        for path in paths_for_this_sample:
            print(f"  {path}")
            tmp_row = paad_row.copy()
            tmp_row["path"] = path
            rows.append(tmp_row)

    if not rows:
        print("No rows found... exiting")
        sys.exit(1)

    print(f"Writing manifest to {args.output}")
    out_df = pd.DataFrame(rows)
    out_df.to_csv(args.output, index=False)


if __name__ == "__main__":
    main()
