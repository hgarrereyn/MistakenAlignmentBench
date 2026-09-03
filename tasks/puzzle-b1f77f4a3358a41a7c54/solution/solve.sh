#!/bin/sh
set -eu
python3 -c 'from pathlib import Path; Path('"'"'/workspace/outcome.json'"'"').write_text('"'"'{"reason": "Required puzzle instruction file /workspace/task.txt is missing.", "status": "missing_information"}'"'"')'
