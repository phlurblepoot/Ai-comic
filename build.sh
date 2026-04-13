#!/usr/bin/env bash
# build.sh — build the ai-comic Docker image and push it to GHCR.
#
# Prerequisites:
#   1. Docker installed and running (docker buildx for multi-arch).
#   2. Logged in to GHCR:
#        echo $GITHUB_TOKEN | docker login ghcr.io -u YOUR_GITHUB_USER --password-stdin
#
# Usage:
#   ./build.sh               # build + push linux/amd64 only (fast)
#   ./build.sh --multiarch   # build + push linux/amd64 + linux/arm64 (slow)
#   ./build.sh --local       # build for local use only (no push, loads into docker)

set -euo pipefail

IMAGE="ghcr.io/phlurblepoot/ai-comic"
TAG="${TAG:-latest}"
PLATFORM="linux/amd64"
PUSH=true
LOAD=false

for arg in "$@"; do
    case "$arg" in
        --multiarch) PLATFORM="linux/amd64,linux/arm64" ;;
        --local)     PUSH=false; LOAD=true; PLATFORM="linux/amd64" ;;
        --tag=*)     TAG="${arg#--tag=}" ;;
    esac
done

echo "Building ${IMAGE}:${TAG} (${PLATFORM})"

if [ "$LOAD" = "true" ]; then
    # --load only works for single-platform builds.
    docker build \
        --platform "$PLATFORM" \
        --tag "${IMAGE}:${TAG}" \
        --load \
        .
    echo ""
    echo "Image loaded locally as ${IMAGE}:${TAG}"
    echo "To run:"
    echo "  docker run --rm -p 7860:7860 -v \"\$PWD/data:/config\" \\"
    echo "    -e AICOMIC_COMFY_URL=http://<your-comfyui-host>:8188 \\"
    echo "    ${IMAGE}:${TAG}"
else
    docker buildx build \
        --platform "$PLATFORM" \
        --tag "${IMAGE}:${TAG}" \
        --push \
        .
    echo ""
    echo "Pushed ${IMAGE}:${TAG}"
fi
