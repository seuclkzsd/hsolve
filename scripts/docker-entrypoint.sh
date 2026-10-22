#!/usr/bin/env bash
# Entry point of the hsolve container image (Dockerfile), with IMAGE = ghcr.io/seuclkzsd/hsolve:
#   docker run --rm IMAGE demo [--threads N ...]   every example solved, checked independently, summary table
#   docker run --rm IMAGE selfcheck                two small examples (scripts/demo.sh --quick)
#   docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/work" IMAGE --A A.npz --sigma 1.0 --k 10 --out out
#                                                  anything else: the hsolve command line, in /work
#   docker run --rm -it IMAGE bash                 a shell (python3 with hsolve, numpy, scipy)
#   docker run --rm IMAGE                          hsolve --help
set -euo pipefail
prefix="${HSOLVE_PREFIX:-/opt/hsolve}"
case "${1:-}" in
  demo) shift; exec "$prefix/scripts/demo.sh" "$@" ;;
  selfcheck) shift; exec "$prefix/scripts/demo.sh" --quick "$@" ;;
  bash|sh|python|python3) exec "$@" ;;
  "") exec "$prefix/bin/hsolve" --help ;;
  *) exec "$prefix/bin/hsolve" "$@" ;;
esac
