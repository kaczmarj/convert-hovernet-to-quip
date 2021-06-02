#!/usr/bin/env python
"""Convert JSON output of HoVerNet to a Quip-compatible format.

This creates a JSON meta file and CSV file of features for each predicted class.
"""

import argparse
import csv
import gzip
import json
from pathlib import Path
from typing import Dict, Set, Union

import openslide
from shapely.geometry import Polygon

PathType = Union[str, Path]


def _is_gzipped(path: PathType) -> bool:
    with open(path, "rb") as f:
        return f.read(2) == b"\x1f\x8b"


def _nuc_prediction_to_quip_dict(d: Dict) -> Dict[str, Union[float, int, str]]:
    area: float = Polygon(d["contour"]).area
    # Converts [[0, 1], [2, 3]] to "0:1:2:3"
    coords = ":".join(":".join(map(str, xy)) for xy in d["contour"])
    coords = f"[{coords}]"
    out: Dict[str, Union[float, int, str]] = {
        "AreaInPixels": area,
        "PhysicalSize": area,
        "ClassId": d["type"],
        "Polygon": coords,
    }
    return out


def write_quip_features_csv(
    hovernet_json: Dict,
    output_path: PathType,
    nuc_type: int = None,
) -> None:
    with open(output_path, "w", newline="") as csvfile:
        fieldnames = ["AreaInPixels", "PhysicalSize", "ClassId", "Polygon"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        prediction: Dict
        for prediction in hovernet_json["nuc"].values():
            # We take only the predictions of a particular type.
            if nuc_type is not None:
                if prediction["type"] == nuc_type:
                    row = _nuc_prediction_to_quip_dict(prediction)
                    writer.writerow(row)
            else:
                row = _nuc_prediction_to_quip_dict(prediction)
                writer.writerow(row)


def write_quip_manifest_json(
    oslide: openslide.OpenSlide,
    output_path: PathType,
    out_file_prefix: str,
    subject_id: str,
    case_id: str,
    analysis_id: str,
    analysis_desc: str = None,
) -> None:
    image_width, image_height = oslide.dimensions
    mppx = oslide.properties[openslide.PROPERTY_NAME_MPP_X]
    mppy = oslide.properties[openslide.PROPERTY_NAME_MPP_Y]
    if mppx != mppy:
        raise ValueError(f"mppx not equal to mppy: {mppx} != {mppy}")
    # Because these predictions apply to the entire whole slide image, we set the tile
    # size equal to the image size. Think of the image as one big tile.
    meta_json = {
        "input_type": "wsi",
        "otsu_ratio": 0.0,
        "curvature_weight": 0.0,
        # TODO: what is this?
        "min_size": 0,
        # TODO: what is this?
        "max_size": 0,
        "ms_kernel": 0,
        "declump_type": 0,
        "levelset_num_iters": 0,
        "mpp": mppx,
        "image_width": image_width,
        "image_height": image_height,
        "tile_minx": 0,
        "tile_miny": 0,
        "tile_width": image_width,
        "tile_height": image_height,
        "patch_minx": 0,
        "patch_miny": 0,
        "patch_width": image_width,
        "patch_height": image_height,
        "output_level": "mask",
        # This is the prefix of the features and algmeta files.
        # The two files are {out_file_prefix}-features.csv and
        # {out_file_prefix}-algmeta.json
        "out_file_prefix": out_file_prefix,
        "subject_id": subject_id,
        "case_id": case_id,
        # This is what comes up in the caMicroscope (to turn on or off).
        "analysis_id": analysis_id,
        "analysis_desc": analysis_desc or analysis_id,
    }

    with open(output_path, "w") as f:
        json.dump(meta_json, f)


class TypedNameSpace(argparse.Namespace):
    def __init__(self):
        self.slide: PathType
        self.subject_id: str
        self.case_id: str
        self.analysis_id: str
        self.analysis_desc: str
        self.input_json: PathType
        self.output_file_prefix: str


def get_parsed_args(args=None) -> TypedNameSpace:
    ns = TypedNameSpace()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--slide", required=True, help="Path to whole slide image.")
    p.add_argument("--subject-id", required=True, help="Subject ID")
    p.add_argument("--case-id", required=True, help="Case ID")
    p.add_argument("--analysis-id", required=True, help="Analysis ID")
    p.add_argument(
        "--analysis-desc",
        help="Analysis description. If omitted, uses analysis ID as description.",
    )
    p.add_argument("input_json", help="Path to HoVerNet output JSON.")
    p.add_argument("output_file_prefix", help="Prefix of output files.")
    args = p.parse_args(args, namespace=ns)
    args.input_json = Path(args.input_json)
    args.slide = Path(args.slide)
    if not args.input_json.exists():
        p.error(f"input JSON file not found: {args.input_json}")
    if not args.slide.exists():
        p.error(f"slide file not found: {args.slide}")
    # Make sure output prefix does not have characters that might mess things up.
    args.output_file_prefix = "".join(
        char for char in args.output_file_prefix if char not in r'\/:*?"<>|'
    )
    return args


def main(args=None) -> None:
    args = get_parsed_args(args)

    print(f"Reading input JSON file {args.input_json}")
    open_fn = gzip.open if _is_gzipped(args.input_json) else open
    with open_fn(args.input_json) as f:  # type: ignore
        hovernet_json = json.load(f)
    print(f"Found {len(hovernet_json['nuc']):,} predicted polygons")

    # Figure out the possible predicted classes. We need to make a CSV+JSON pair for
    # each class.
    nuc_types: Set[int] = {d["type"] for d in hovernet_json["nuc"].values()}
    print(f"Found {len(nuc_types)} predicted classes: {nuc_types}")

    print(f"Opening slide: {args.slide}")
    oslide = openslide.OpenSlide(str(args.slide))

    print("-" * 40)
    for nuc_type in nuc_types:
        print(f"Working on nuclear prediction type {nuc_type}")
        out_file_prefix = f"{args.output_file_prefix}_type{nuc_type}"
        features_file = f"{out_file_prefix}-features.csv"
        print(f"Writing features to {features_file}")
        write_quip_features_csv(
            hovernet_json=hovernet_json,
            output_path=features_file,
            nuc_type=nuc_type,
        )
        algmeta_file = f"{out_file_prefix}-algmeta.json"
        print(f"Writing manifest to {algmeta_file}")
        write_quip_manifest_json(
            oslide=oslide,
            output_path=algmeta_file,
            out_file_prefix=args.output_file_prefix,
            subject_id=args.subject_id,
            case_id=args.case_id,
            analysis_id=args.analysis_id,
            analysis_desc=args.analysis_desc,
        )
        print("-" * 40)

    print("Finished")


if __name__ == "__main__":
    main()
