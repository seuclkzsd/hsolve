# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
"""Evidence for the showcase pages (docs/showcase/): the hard-scenario campaign against SLEPc, the
physics checks against closed-form solutions, and the figures and tables generated from their data.

Data flow (every number on the pages comes from a committed JSON file written by these tools):

    scenarios.py  catalogue of the hard scenarios; `prepare` builds the campaign data root
    waveguide_ref.py  certified discrete reference of hollow waveguide cases (TE/TM families)
    campaign.py   runs hsolve / SLEPc default / SLEPc tuned per scenario -> results/showcase/raw/;
                  `tune` tunes SLEPc for scenarios without a case profile -> results/showcase/slepc_tuning.json
    slepc_probe.py  records SLEPc's own error for configurations it does not support
    physics.py    PEC cavity and square waveguide against analytic solutions -> results/showcase/physics/
    tables.py     raw data -> results/showcase/scenarios.{json,md}, the generated page sections and the
                  README quotes in results/showcase/README.md
    figures.py    committed data -> docs/images/*.png|svg (matplotlib only)

`tools/showcase/run_all.sh` is the exact sequence used on the cluster.
"""
