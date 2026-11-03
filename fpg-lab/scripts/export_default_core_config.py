from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fpg_lab.core.settings import ROOT
from fpg_lab.integrations.fpg_core.config_codec import (
    CoreConfigCodec,
    CoreConfigurationError,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and export the normalized current Lab starter profile. "
            "This does not regenerate policy from Core defaults."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "seed/system_configuration.default.json",
    )
    parser.add_argument("--name", default="research-default")
    parser.add_argument(
        "--description",
        default=None,
        help=(
            "Optional record description. By default, the installed fpg-core "
            "version and configuration schema version are included."
        ),
    )
    args = parser.parse_args()

    try:
        validated = CoreConfigCodec().default_configuration()
    except CoreConfigurationError as exc:
        print(f"Configuration export failed:\n{exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    schema_version = str(validated.payload["schema_version"])
    description = args.description or (
        f"Lab schema {schema_version} research profile validated with "
        f"fpg-core {validated.fpg_core_version}. Review example setbacks "
        "and room references before non-research use."
    )
    document = {
        "name": args.name,
        "description": description,
        "schema_version": schema_version,
        "configuration_data": validated.payload,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Exported validated fpg-core {validated.fpg_core_version} "
        f"schema {schema_version} configuration to {args.output}"
    )


if __name__ == "__main__":
    main()
