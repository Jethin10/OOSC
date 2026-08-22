from pathlib import Path
from oosc.adapters.tau2_export import write_export
for dom in ["retail", "airline"]:
    d, t = write_export(dom, Path("results/repro/schema"))
    print("wrote", d, t)
