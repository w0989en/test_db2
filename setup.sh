#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

driver_version=12.1.5.0
driver="lib/jcc-${driver_version}.jar"
base="https://repo.maven.apache.org/maven2/com/ibm/db2/jcc/${driver_version}/jcc-${driver_version}.jar"
mkdir -p lib data
if [[ ! -f "$driver" ]]; then
    curl --fail --location --retry 3 --output "${driver}.tmp" "$base"
    curl --fail --location --retry 3 --output "${driver}.sha1.tmp" "${base}.sha1"
    mv "${driver}.tmp" "$driver"
    mv "${driver}.sha1.tmp" "${driver}.sha1"
fi
[[ -f "${driver}.sha1" ]] || { echo "Missing published driver checksum" >&2; exit 1; }
expected="$(tr -d '\r\n ' < "${driver}.sha1")"
printf '%s  %s\n' "$expected" "$driver" | sha1sum --check --status

mkdir -p .local/classes
java com.sun.tools.javac.Main -d .local/classes JdbcBenchmark.java

if [[ ! -f data/rows.del ]]; then
    python3 generate_data.py --rows 1000000 --output data/rows.del
fi
actual="$(wc -l < data/rows.del)"
[[ "$actual" -eq 1000000 ]] || { echo "Expected 1000000 rows, got $actual" >&2; exit 1; }
echo "Ready: $driver and $actual data rows"
