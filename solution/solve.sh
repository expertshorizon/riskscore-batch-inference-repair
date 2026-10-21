#!/bin/bash
set -euo pipefail
source_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/app"
rm -rf /app/riskscore_engine
mkdir -p /app/riskscore_engine
cp -R "$source_dir/riskscore_engine/." /app/riskscore_engine/
install -m 0755 "$source_dir/score_batch.py" /app/score_batch.py
install -m 0644 "$source_dir/SPEC.md" /app/SPEC.md
python -m compileall -q /app/riskscore_engine /app/score_batch.py
