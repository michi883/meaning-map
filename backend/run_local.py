#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

from backend.core.pipeline import MeaningMapPipeline
from backend.core.schemas import MeaningMapRequest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MeaningMap pipeline locally")
    parser.add_argument(
        "--payload-file",
        type=Path,
        default=Path("sample_request.json"),
        help="Path to request JSON payload",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        help="Optional path to write result JSON",
    )
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    load_dotenv()

    payload = json.loads(args.payload_file.read_text())
    request = MeaningMapRequest.model_validate(payload)

    pipeline = MeaningMapPipeline.from_env()
    result = await pipeline.run(request)

    output = json.dumps(result.model_dump(mode="json"), indent=2)
    if args.output_file:
        args.output_file.write_text(output)
    print(output)


if __name__ == "__main__":
    asyncio.run(_main())
