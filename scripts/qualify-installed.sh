#!/bin/sh
# Run contract tests from a wheel with no source checkout on Python's path.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
output=${1:?usage: qualify-installed.sh ABSOLUTE_OUTPUT_DIRECTORY}
case "$output" in /*) ;; *) echo 'Output directory must be absolute' >&2; exit 2;; esac
mkdir -p "$output/packages"
consumer=$(mktemp -d "${TMPDIR:-/tmp}/publishing-consumer.XXXXXX")
trap 'rm -rf "$consumer"' EXIT HUP INT TERM
uv build "$repo" --out-dir "$output/packages"
version=$(uv run --directory "$repo" python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')
wheel="$output/packages/amplifier_publishing-$version-py3-none-any.whl"
uv venv "$consumer/env"
uv pip install --python "$consumer/env/bin/python" "$wheel" 'pytest==9.1.1'
mkdir "$consumer/tests"
cp "$repo"/tests/test_*.py "$consumer/tests/"
cd "$consumer"
"$consumer/env/bin/python" -I -c '
import hashlib, importlib.metadata, json, pathlib, sys
import amplifier_publishing
wheel, output = map(pathlib.Path, sys.argv[1:])
origin = pathlib.Path(amplifier_publishing.__file__).resolve()
assert origin.is_relative_to(pathlib.Path(sys.prefix).resolve())
assert not any(name.startswith(("amplifier_unified", "amplifier_core", "amplifier_foundation")) for name in sys.modules)
(output / "installed-package.json").write_text(json.dumps({
    "version": importlib.metadata.version("amplifier-publishing"),
    "python": sys.version, "importOrigin": str(origin),
    "wheel": str(wheel), "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
    "sourceCheckoutOnImportPath": False,
}, indent=2) + "\n")
' "$wheel" "$output"
"$consumer/env/bin/python" -I -m pytest tests -q -ra --junitxml="$output/installed-contracts.xml"
