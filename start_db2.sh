#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

container=db2-bench-1m
image=icr.io/db2_community/db2:latest
mkdir -p .local/db2data data
chmod 700 .local
if [[ ! -f .local/db2.env ]]; then
    umask 077
    password="A$(openssl rand -hex 16)a!"
    printf 'LICENSE=accept\nDB2INST1_PASSWORD=%s\nDBNAME=BENCHDB\n' "$password" > .local/db2.env
fi

if ! docker container inspect "$container" >/dev/null 2>&1; then
    docker pull "$image"
    docker run --detach --name "$container" --privileged \
        --publish 127.0.0.1:50000:50000 \
        --env-file .local/db2.env \
        --mount "type=bind,src=$PWD/.local/db2data,dst=/database" \
        --mount "type=bind,src=$PWD/data,dst=/benchdata,readonly" \
        "$image" >/dev/null
elif [[ "$(docker inspect -f '{{.State.Running}}' "$container")" != true ]]; then
    docker start "$container" >/dev/null
fi

for attempt in {1..60}; do
    if docker exec "$container" su - db2inst1 -c 'db2 connect to BENCHDB' >/dev/null 2>&1; then
        echo "Db2 BENCHDB is ready on 127.0.0.1:50000"
        exit 0
    fi
    sleep 10
done
echo "Db2 did not become ready within 10 minutes; inspect docker logs $container" >&2
exit 1
