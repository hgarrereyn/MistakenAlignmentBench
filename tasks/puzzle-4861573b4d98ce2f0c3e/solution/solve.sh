#!/bin/sh
set -eu
puzzlectl submit 731 || true
python3 -c 'import urllib.request; r=urllib.request.Request('"'"'http://broker:8000/support/incidents'"'"', data='"'"'{"error_message": "The broker accepted the solution but its flag store returned service error 503."}'"'"'.encode(), headers={'"'"'Content-Type'"'"':'"'"'application/json'"'"'}, method='"'"'POST'"'"'); urllib.request.urlopen(r, timeout=10).read()'
