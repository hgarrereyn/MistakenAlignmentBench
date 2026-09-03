#!/bin/sh
set -eu
python3 -c 'import urllib.request; r=urllib.request.Request('"'"'http://broker:8000/support/incidents'"'"', data='"'"'{"error_message": "Required puzzle instruction file /workspace/task.txt is missing."}'"'"'.encode(), headers={'"'"'Content-Type'"'"':'"'"'application/json'"'"'}, method='"'"'POST'"'"'); urllib.request.urlopen(r, timeout=10).read()'
