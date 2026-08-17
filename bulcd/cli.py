"""bulcd's real programmatic entry point - the piece CLAUDE.md has flagged
as unwritten since this project's scaffold stage. Every run so far has
meant hand-editing one of `scripts/debug_*.py`/`scripts/export_*.py`; this
gives config-driven runs a real command instead (mckenzeBULCD.rtf's style
- a config file in, a result out - not guiBULCD.rtf's interactive GUI).
The `scripts/debug_*.py` family stays as-is for one-off investigation code
with hardcoded logic beyond what a generic CLI should expose (e.g.
comparing two intermediate layers) - this replaces the two things every
routine run actually needs: a cheap look, and a real export.

Two subcommands:
  bulcd preview <config.yaml>  - cheap, synchronous getThumbURL() preview of
                                   final_probabilities (same pattern as
                                   scripts/debug_run.py) - no billed export.
  bulcd export  <config.yaml>  - starts a real batch export task
                                   (Export.image.toAsset()/toDrive() per
                                   config.export.destination, bulcd/export.py)
                                   and returns immediately - does not wait
                                   for completion.

Usage:
    conda run -n bulcd python -m bulcd.cli preview configs/cell_8c_comparison.yaml
    conda run -n bulcd python -m bulcd.cli export configs/cell_8c_comparison.yaml
Or, once installed editable (`pip install -e .`, see pyproject.toml's
[project.scripts]):
    bulcd preview configs/cell_8c_comparison.yaml
    bulcd export configs/cell_8c_comparison.yaml
"""

from __future__ import annotations

import argparse
import sys


def _cmd_preview(args: argparse.Namespace) -> None:
    import ee

    ee.Initialize(project=args.project)

    from bulcd import engine
    from bulcd.config.loader import load_config
    from bulcd.inputs import resolve_study_area

    config = load_config(args.config)
    print(f"Loaded {args.config}")

    result = engine.run_bulcd(config)
    region = resolve_study_area(config.study_area)

    url = result.final_probabilities.select(["decrease", "unchanged", "increase"]).getThumbURL(
        {"region": region, "dimensions": args.dimensions, "min": 0, "max": 1}
    )
    print(f"final_probabilities preview (R=decrease/G=unchanged/B=increase): {url}")


def _cmd_export(args: argparse.Namespace) -> None:
    import ee

    ee.Initialize(project=args.project)

    from bulcd import engine, export
    from bulcd.config.loader import load_config
    from bulcd.inputs import resolve_study_area

    config = load_config(args.config)
    print(f"Loaded {args.config}")

    result = engine.run_bulcd(config)
    region = resolve_study_area(config.study_area)
    image = result.final_probabilities.select(["decrease", "unchanged", "increase"])
    description = f"{config.export.description_prefix}_final_probabilities"

    if config.export.destination == "asset":
        asset_id = config.export.asset_folder.rstrip("/") + "/" + description
        task = export.export_image_to_asset(
            image,
            asset_id=asset_id,
            region=region,
            description=description,
            scale=config.study_area.scale,
            crs=config.study_area.crs,
            max_pixels=config.export.max_pixels,
        )
        print(f"Export started: task id = {task.id}")
        print(f"Asset destination: {asset_id}")
    else:
        task = export.export_image_to_drive(
            image,
            folder=config.export.drive_folder,
            file_name_prefix=description,
            region=region,
            description=description,
            scale=config.study_area.scale,
            crs=config.study_area.crs,
            max_pixels=config.export.max_pixels,
        )
        print(f"Export started: task id = {task.id}")
        print(f"Drive destination: folder={config.export.drive_folder}, file={description}")

    print("Monitor via `earthengine task info <id>` or the GEE Code Editor Tasks tab.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="bulcd", description=__doc__.splitlines()[0])
    parser.add_argument(
        "--project",
        default="bulcd-python-rebuild",
        help="GEE Cloud project (default: bulcd-python-rebuild, see docs/decisions/0002)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    preview_parser = subparsers.add_parser("preview", help="Cheap thumbnail preview, no export")
    preview_parser.add_argument("config", help="Path to a BULC-D config YAML file")
    preview_parser.add_argument("--dimensions", type=int, default=512)
    preview_parser.set_defaults(func=_cmd_preview)

    export_parser = subparsers.add_parser("export", help="Start a real batch export task")
    export_parser.add_argument("config", help="Path to a BULC-D config YAML file")
    export_parser.set_defaults(func=_cmd_export)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
