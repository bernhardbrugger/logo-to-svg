"""Turn blurry raster logos into clean, scalable SVGs."""
__version__ = "0.2.0"

from .core import vectorize  # noqa: E402
from .util import LogoError  # noqa: E402

__all__ = ["vectorize", "LogoError", "__version__"]
