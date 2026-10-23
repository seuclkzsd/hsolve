# syntax=docker/dockerfile:1
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
# hsolve container image (docs/INSTALL.md):
#   build stage   the project's conda-forge toolchain (env/environment.yml), MUMPS 5.8.2 from
#                 third_party/ with the project's patches, the portable release preset and the
#                 relocatable package of tools/release/package.sh (its checks run here too);
#   runtime stage that package under /opt/hsolve plus Python with numpy and scipy (the demo's
#                 independent check and the Python module), running as an unprivileged user.
#
#   docker build -t hsolve .
#   docker run --rm hsolve demo                       solve every example, check, print a table
#   docker run --rm hsolve selfcheck                  two small examples (scripts/demo.sh --quick)
#   docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/work" hsolve \
#       --A A.npz --B B.npz --sigma -0.5 --k 18 --out result
# Published by .github/workflows/release.yml as ghcr.io/seuclkzsd/hsolve:<version> on tags v*.
ARG MICROMAMBA_IMAGE=mambaorg/micromamba:2.8.1-debian12-slim

# ---------------------------------------------------------------------------------------- build
FROM ${MICROMAMBA_IMAGE} AS build
USER root
# binutils: objdump / readelf / strip for the package checks, in case the environment's
# activation does not name its own (OBJDUMP, READELF, STRIP); patch(1) for the MUMPS patches.
RUN apt-get update \
 && apt-get install -y --no-install-recommends binutils patch \
 && rm -rf /var/lib/apt/lists/*
USER $MAMBA_USER
COPY --chown=$MAMBA_USER:$MAMBA_USER env/environment.yml /tmp/environment.yml
RUN micromamba install -y -n base -f /tmp/environment.yml \
 && micromamba clean --all --yes
WORKDIR /home/mambauser/hsolve
COPY --chown=$MAMBA_USER:$MAMBA_USER . .
# Every RUN below runs in the activated base environment (compilers, CMake, libraries).
ARG MAMBA_DOCKERFILE_ACTIVATE=1
ARG HSOLVE_VERSION=dev
ARG HSOLVE_COMMIT=unknown
ARG SOURCE_DATE_EPOCH=0
# Only what the package holds: no unit tests, benchmarks or MPI launcher; warnings are errors.
# HS_MIN_AVAIL_GB: a build machine is not shared, tools/run/guard.py need not keep 12 GiB free.
ENV HS_MUMPS_CACHE=/home/mambauser/mumps-cache \
    HS_MIN_AVAIL_GB=1 \
    HS_CMAKE_ARGS="-DHSOLVE_BUILD_TESTS=OFF -DHSOLVE_BUILD_BENCH=OFF -DHSOLVE_WITH_MPI=OFF -DHSOLVE_WERROR=ON"
# The image runs on Debian 12 (glibc 2.36); the release tarball itself is checked against 2.17.
RUN HSOLVE_COMMIT="${HSOLVE_COMMIT}" SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH}" \
    tools/release/package.sh --out /home/mambauser/package --version "${HSOLVE_VERSION}" --glibc-max 2.36 \
 && tar -xzf "/home/mambauser/package/hsolve-${HSOLVE_VERSION}-linux-x86_64.tar.gz" -C /home/mambauser \
 && mv "/home/mambauser/hsolve-${HSOLVE_VERSION}-linux-x86_64" /home/mambauser/hsolve-prefix

# -------------------------------------------------------------------------------------- runtime
FROM ${MICROMAMBA_IMAGE} AS runtime
ARG HSOLVE_VERSION=dev
LABEL org.opencontainers.image.title="hsolve" \
      org.opencontainers.image.description="Certified shift-invert eigensolver for large sparse Hermitian (indefinite, generalized) eigenproblems" \
      org.opencontainers.image.source="https://github.com/seuclkzsd/hsolve" \
      org.opencontainers.image.version="${HSOLVE_VERSION}" \
      org.opencontainers.image.licenses="Apache-2.0"
# The versions of env/environment.yml: the module is built for CPython 3.11.
RUN micromamba install -y -n base -c conda-forge python=3.11 numpy=2.4 scipy=1.17 \
 && micromamba clean --all --yes
COPY --from=build /home/mambauser/hsolve-prefix /opt/hsolve
COPY --chmod=0755 scripts/docker-entrypoint.sh /usr/local/bin/hsolve-entrypoint
USER root
RUN mkdir -p /work && chown "$MAMBA_USER:$MAMBA_USER" /work
USER $MAMBA_USER
ENV PATH=/opt/hsolve/bin:$PATH \
    PYTHONPATH=/opt/hsolve/python \
    HSOLVE_PREFIX=/opt/hsolve
WORKDIR /work
# _entrypoint.sh (micromamba image) activates the base environment, then runs hsolve-entrypoint:
# "demo" / "selfcheck" -> scripts/demo.sh, a shell or python as given, anything else -> hsolve.
ENTRYPOINT ["/usr/local/bin/_entrypoint.sh", "/usr/local/bin/hsolve-entrypoint"]
CMD []
