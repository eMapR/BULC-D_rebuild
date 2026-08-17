"""Batch export to the user's own GEE assets - the piece CLAUDE.md has
flagged as unwritten since this project's scaffold stage.

Every debug script so far (`scripts/debug_*.py`) uses `ee.Image.getThumbURL()`
- a cheap, synchronous PREVIEW render, capped in both resolution and
compute budget (see CLAUDE.md "Year of change"'s "User memory limit
exceeded" finding for a concrete case where that cap was hit). A real,
full-resolution map needs an actual batch export job instead -
`ee.batch.Export.image.toAsset()`, which runs asynchronously on Earth
Engine's batch compute tier (not subject to the interactive tier's memory
limit) and writes the result into the user's own GEE assets.

Deliberately thin: this module starts a task and hands it back so a
caller can poll `.status()` if it wants to, but doesn't wait for
completion - `Export.image.toAsset()` jobs can take anywhere from minutes
to hours depending on region size/resolution, and blocking a script on
that isn't useful for a script whose job is just to kick the export off.
"""

from __future__ import annotations

import ee


def export_image_to_asset(
    image: ee.Image,
    asset_id: str,
    region: ee.Geometry,
    description: str,
    scale: int = 30,
    crs: str = "EPSG:4326",
    max_pixels: int = int(1e13),
) -> ee.batch.Task:
    """Starts (not just builds) an Export.image.toAsset() batch task.

    `asset_id` must be a full asset path the caller has write access to
    (e.g. "projects/<project>/assets/<name>") - this function does not
    create parent folders or validate the destination exists; an invalid
    path fails at task-start time with an EE-side error, not here.

    Returns the started ee.batch.Task. Progress is visible via
    `task.status()`, the GEE Code Editor's Tasks tab, or
    `earthengine task list` - this function does not poll or block.
    """
    task = ee.batch.Export.image.toAsset(
        image=image,
        description=description,
        assetId=asset_id,
        region=region,
        scale=scale,
        crs=crs,
        maxPixels=max_pixels,
    )
    task.start()
    return task


def export_image_to_drive(
    image: ee.Image,
    folder: str,
    file_name_prefix: str,
    region: ee.Geometry,
    description: str,
    scale: int = 30,
    crs: str = "EPSG:4326",
    max_pixels: int = int(1e13),
) -> ee.batch.Task:
    """Starts (not just builds) an Export.image.toDrive() batch task.

    Same posture as export_image_to_asset() above - `ExportConfig.destination
    == "drive"` was already a validated config path (bulcd/config/loader.py)
    with no corresponding export function until now.
    """
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=description,
        folder=folder,
        fileNamePrefix=file_name_prefix,
        region=region,
        scale=scale,
        crs=crs,
        maxPixels=max_pixels,
    )
    task.start()
    return task
