#!/usr/bin/env bash
set -euo pipefail

fresh="No"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --fresh)
            fresh="${2:?--fresh requires Yes or No}"
            shift 2
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: bash scripts/setup_ubuntu.sh [--fresh Yes|No]" >&2
            exit 2
            ;;
    esac
done

case "${fresh,,}" in
    yes) fresh="Yes" ;;
    no) fresh="No" ;;
    *)
        echo "--fresh must be Yes or No" >&2
        exit 2
        ;;
esac

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_root"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3.11 or newer is required. Install the documented prerequisites first." >&2
    exit 1
fi

python3 -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11+ is required'; print(sys.version)"

if [[ ! -x .venv/bin/python ]]; then
    python3 -m venv .venv
fi

resolved_core_path="$(cd "$repository_root/.." && pwd)"
if [[ ! -f "$resolved_core_path/pyproject.toml" ]]; then
    echo "fpg-core pyproject.toml was not found at $resolved_core_path" >&2
    exit 1
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e "$resolved_core_path" -e ".[dev]"

if [[ ! -f .env ]]; then
    cp .env.example .env
fi

if [[ "$fresh" == "Yes" ]]; then
    .venv/bin/python -m scripts.reset_db --yes
fi

.venv/bin/python -m scripts.init_db
.venv/bin/python -m scripts.verify_fpg_core --system-config seed/system_configuration.default.json
.venv/bin/python -m scripts.seed_db \
    --system-config seed/system_configuration.default.json \
    --activate \
    --floor-plan-template seed/floor_plan_template.example.json \
    --floor-plan-template seed/floor_plan_template.garage_veranda.json \
    --floor-plan-template seed/floor_plan_template.two_bedroom_ensuite.json \
    --floor-plan-template seed/floor_plan_template.three_bedroom_ensuites.json

echo
echo "FPG Lab initialization completed."
echo "Start the Lab with:"
echo ".venv/bin/python -m fpg_lab"
