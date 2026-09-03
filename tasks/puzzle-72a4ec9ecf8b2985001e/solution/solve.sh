#!/bin/sh
set -eu
python3 -c 'from pathlib import Path; Path('"'"'/workspace/outcome.json'"'"').write_text('"'"'{"reason": "No solution: gcd(a,m) is 6, which does not divide target-b.", "status": "no_solution"}'"'"')'
