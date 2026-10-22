"""Evidence for the showcase pages (docs/showcase/): the hard-scenario campaign against SLEPc, the
physics checks against closed-form solutions, and the figures and tables generated from their data.

Data flow (every number on the pages comes from a committed JSON file written by these tools):

    scenarios.py  catalogue of the hard scenarios; `prepare` builds the campaign data root
    waveguide_ref.py  certified discrete reference of hollow waveguide cases (TE/TM families)
    campaign.py   runs hsolve / SLEPc default / SLEPc tuned per scenario -> results/showcase/raw/
    slepc_probe.py  records SLEPc's own error for configurations it does not support
    physics.py    PEC cavity and square waveguide against analytic solutions -> results/showcase/physics/
    tables.py     raw data -> results/showcase/scenarios.{json,md} and the generated page sections
    figures.py    committed data -> docs/images/*.png|svg (matplotlib only)

`tools/showcase/run_all.sh` is the exact sequence used on the cluster.
"""
