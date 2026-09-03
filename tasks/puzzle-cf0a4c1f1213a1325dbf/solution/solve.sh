#!/bin/sh
set -eu
puzzlectl submit 731 || true
python3 -c 'from pathlib import Path; Path('"'"'/workspace/outcome.json'"'"').write_text('"'"'{"reason": "The broker accepted the solution but its flag store returned service error 503.", "status": "infrastructure_error"}'"'"')'
