from .coachlenz import scan as scan_coachlenz
from .programpilot import scan as scan_programpilot
from .cravyn import scan as scan_cravyn
from .flypilot import scan as scan_flypilot
from .preclose import scan as scan_preclose
from .equityforge import scan as scan_equityforge
from .ledgerlux import scan as scan_ledgerlux
from .cosby_capital import scan as scan_cosby_capital

ALL_SCANNERS = [
    scan_coachlenz,
    scan_programpilot,
    scan_cravyn,
    scan_flypilot,
    scan_preclose,
    scan_equityforge,
    scan_ledgerlux,
    scan_cosby_capital,
]
