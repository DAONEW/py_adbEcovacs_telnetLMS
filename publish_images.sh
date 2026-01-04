#!/usr/bin/env bash

# Build and push both service images to GHCR using the local Dockerfiles.
# Accepts GHCR_OWNER (required), optional GHCR_PAT for login, and TAG (optional override).
# When TAG is omitted the script automatically bumps `.image_version`, uses that integer as
# the tag, and also retags the build as `latest`.

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

readonly OWNER="daonew/py_adbecovacs_telnetlms"
explicit_tag="${TAG:-}"

if [[ -z "$OWNER" ]]; then
  echo "GHCR_OWNER is required (GitHub username/org that owns the images)." >&2
  exit 1
fi

if [[ -n "${GHCR_PAT:-}" ]]; then
  echo "Logging into ghcr.io as '$OWNER'..."
  echo "$GHCR_PAT" | docker login ghcr.io -u "$OWNER" --password-stdin
else
  echo "GHCR_PAT not set; assuming docker is already logged into ghcr.io."
fi

declare -A targets=(
  [telnet_squeezelite]="telnet_squeezelite/Dockerfile"
  [adb_ecovacs]="adb_ecovacs/Dockerfile"
)

version_file="$root_dir/.image_version"
if [[ -n "$explicit_tag" ]]; then
  TAG="$explicit_tag"
  echo "Using override tag: $TAG"
else
  version=0
  if [[ -f "$version_file" ]]; then
    version=$(<"$version_file")
  fi
  version=$((version + 1))
  printf "%s\n" "$version" > "$version_file"
  TAG="$version"
  echo "Auto-incremented release tag to $TAG (update and commit $version_file if you want to track this change)."
fi

for image in "${!targets[@]}"; do
  dockerfile="${targets[$image]}"
  version_tag="ghcr.io/$OWNER/$image:$TAG"
  latest_tag="ghcr.io/$OWNER/$image:latest"
  echo "Building $image from $dockerfile (tag: $TAG)..."
  docker build -f "$root_dir/$dockerfile" -t "$version_tag" -t "$latest_tag" "$root_dir"
  echo "Pushing $version_tag and $latest_tag..."
  docker push "$version_tag"
  docker push "$latest_tag"
done

echo "All images built and pushed with tag '$TAG' (latest tag refreshed as well)."
