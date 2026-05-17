"""tirtha — open humanitarian accessibility mapping.

A Python pipeline that estimates walking-time to nearest essential service
(clinics, schools, water points, shelters, polling stations, …) for any
populated region of the world. Uses only public data infrastructure:
Sentinel-1/2 + NASADEM via Microsoft Planetary Computer, OpenStreetMap,
WorldPop, IBM/ESA TerraMind. No paid APIs, no registration walls.

Tirtha is opinionated for healthcare as the flagship demo and benchmark
(MAP 2020 from Weiss et al. is the comparator) — but the technical pipeline
is application-general; healthcare is a configuration choice.

See docs/methodology.md for the design and docs/plain_english.md for the
project explained without jargon.
"""

__version__ = "0.1.0"
__author__ = "Adam Munawar Rahman"
__license__ = "Apache-2.0"

from tirtha.pipeline import run_accessibility

__all__ = ["run_accessibility", "__version__"]
