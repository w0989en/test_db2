#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

container=db2-bench-1m
source_image=icr.io/db2_community/db2@sha256:2de8151713c261843868c5c3411b57be6ae79d99d70a5b3022337836776bfda6
image="$source_image"
mkdir -p .local/db2data data
chmod 700 .local
if [[ ! -f .local/db2.env ]]; then
    umask 077
    password="A$(openssl rand -hex 16)a!"
    printf 'LICENSE=accept\nDB2INST1_PASSWORD=%s\nDBNAME=BENCHDB\n' "$password" > .local/db2.env
fi

if ! docker container inspect "$container" >/dev/null 2>&1; then
    if [[ "$(docker info --format '{{.Driver}}')" == vfs ]]; then
        ./prepare_db2_image.sh "$source_image"
        image=db2-bench-compact:verified
    else
        docker pull "$image"
    fi
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
    if docker logs "$container" 2>&1 | rg 'Setup has completed\.' >/dev/null &&
       docker exec "$container" su - db2inst1 -c 'db2 connect to BENCHDB' >/dev/null 2>&1; then
        echo "Db2 BENCHDB is ready on 127.0.0.1:50000"
        exit 0
    fi
    sleep 10
done
echo "Db2 did not become ready within 10 minutes; inspect docker logs $container" >&2
exit 1
