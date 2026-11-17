#!/usr/bin/env bash
# Unpack Python's C headers (python3.12-dev, libpython3.12-dev) into .tools/python-headers/ (AC7.1.6).
# Triton's GPU helper compiles C code that includes Python.h. No root, nothing outside this folder:
# the two .deb files are downloaded into .cache/debs/ and unpacked with dpkg-deb -x. Safe to run again.
set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/.tools/python-headers"
HEADER="$DEST/usr/include/python3.12/Python.h"

if [ -f "$HEADER" ]; then
  echo "Python.h already in place: $HEADER"
  exit 0
fi

version="$(dpkg-query -W -f='${Version}' python3.12)"
mkdir -p "$ROOT/.cache/debs" "$DEST"
cd "$ROOT/.cache/debs"
apt-get download "python3.12-dev=$version" "libpython3.12-dev=$version"
for deb in python3.12-dev_*.deb libpython3.12-dev_*.deb; do
  dpkg-deb -x "$deb" "$DEST"
done

if [ ! -f "$HEADER" ]; then
  echo "Python.h not found after unpacking: $HEADER" >&2
  exit 1
fi
echo "Python.h unpacked to: $HEADER"
