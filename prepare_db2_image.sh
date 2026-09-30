#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Flatten the verified filesystem to avoid vfs retaining a full copy per layer.
source_image="${1:?Pass the pinned source image reference}"
compact_image=db2-bench-compact:verified
if [[ "$(docker image inspect "$compact_image" --format '{{index .Config.Labels "bench.source"}}' 2>/dev/null || true)" == "$source_image" ]]; then
    exit 0
fi
mkdir -p .local/bin
if [[ ! -x .local/bin/crane ]]; then
    release=https://github.com/google/go-containerregistry/releases/download/v0.20.3
    curl --fail --location --retry 3 --output .local/go-containerregistry_Linux_x86_64.tar.gz "$release/go-containerregistry_Linux_x86_64.tar.gz"
    curl --fail --location --retry 3 --output .local/crane-checksums.txt "$release/checksums.txt"
    rg ' go-containerregistry_Linux_x86_64.tar.gz$' .local/crane-checksums.txt > .local/crane-checksum.selected
    (cd .local && sha256sum --check crane-checksum.selected)
    tar -xzf .local/go-containerregistry_Linux_x86_64.tar.gz -C .local/bin crane
fi
.local/bin/crane config "$source_image" > .local/db2-image-config.json
if [[ ! -f .local/db2-image.tar ]]; then
    .local/bin/crane pull "$source_image" .local/db2-image.tar.tmp
    mv .local/db2-image.tar.tmp .local/db2-image.tar
fi
.local/bin/crane validate --tarball .local/db2-image.tar
python3 - "$source_image" "$compact_image" <<'PY'
import json
import subprocess
import sys

source, target = sys.argv[1:]
with open(".local/db2-image-config.json") as file:
    config = json.load(file)["config"]
changes = []
for entry in config.get("Env", []):
    name, value = entry.split("=", 1)
    changes.extend(["--change", f"ENV {name}={json.dumps(value)}"])
for key in ("Entrypoint", "Cmd"):
    if config.get(key):
        changes.extend(["--change", key.upper() + " " + json.dumps(config[key])])
for key, directive in (("WorkingDir", "WORKDIR"), ("User", "USER")):
    if config.get(key):
        changes.extend(["--change", directive + " " + config[key]])
if config.get("Volumes"):
    changes.extend(["--change", "VOLUME " + json.dumps(list(config["Volumes"]))])
for port in config.get("ExposedPorts", {}):
    changes.extend(["--change", "EXPOSE " + port])
for name, value in config.get("Labels", {}).items():
    changes.extend(["--change", f"LABEL {name}={json.dumps(value)}"])
changes.extend(["--change", "LABEL bench.source=" + json.dumps(source)])
with open(".local/db2-image.tar", "rb") as archive:
    exporter = subprocess.Popen([".local/bin/crane", "export", "-", "-"],
                                stdin=archive, stdout=subprocess.PIPE)
    importer = subprocess.run(["docker", "import", *changes, "-", target], stdin=exporter.stdout)
    exporter.stdout.close()
    export_status = exporter.wait()
if importer.returncode or export_status:
    subprocess.run(["docker", "image", "rm", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sys.exit(importer.returncode or export_status)
PY
rm .local/db2-image.tar
