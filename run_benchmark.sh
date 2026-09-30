#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

./setup.sh
./start_db2.sh
set -a
# The env file is generated locally and excluded from Git.
source .local/db2.env
set +a
export DB2_URL=jdbc:db2://127.0.0.1:50000/BENCHDB
export DB2_USER=db2inst1
export DB2_PASSWORD="$DB2INST1_PASSWORD"
driver=lib/jcc-12.1.5.0.jar
classpath="$driver:.local/classes"
java -cp "$classpath" JdbcBenchmark prepare
cat data/rows.del > /dev/null

start_ns="$(date +%s%N)"
docker exec db2-bench-1m su - db2inst1 -c \
    'db2 connect to BENCHDB >/dev/null && db2 "LOAD FROM /benchdata/rows.del OF DEL MESSAGES /tmp/bench_load.msg INSERT INTO BENCH_LOAD NONRECOVERABLE"'
load_ns="$(( $(date +%s%N) - start_ns ))"
load_rows="$(java -cp "$classpath" JdbcBenchmark count BENCH_LOAD)"
[[ "$load_rows" -eq 1000000 ]] || { echo "LOAD row count: $load_rows" >&2; exit 1; }

start_ns="$(date +%s%N)"
java -cp "$classpath" JdbcBenchmark insert data/rows.del 1000
jdbc_ns="$(( $(date +%s%N) - start_ns ))"
jdbc_rows="$(java -cp "$classpath" JdbcBenchmark count BENCH_JDBC)"
[[ "$jdbc_rows" -eq 1000000 ]] || { echo "JDBC row count: $jdbc_rows" >&2; exit 1; }

result_file=benchmark-results.csv
{
    printf 'method,seconds,rows,rows_per_second\n'
    awk -v ns="$load_ns" -v rows="$load_rows" 'BEGIN { sec=ns/1000000000; printf "LOAD,%.3f,%d,%.0f\n", sec, rows, rows/sec }'
    awk -v ns="$jdbc_ns" -v rows="$jdbc_rows" 'BEGIN { sec=ns/1000000000; printf "JDBC,%.3f,%d,%.0f\n", sec, rows, rows/sec }'
} > "${result_file}.tmp"
mv "${result_file}.tmp" "$result_file"
cat "$result_file"
