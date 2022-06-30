import importlib

from slicer.util import pip_install

from .slicer_constants import REQUIRED_MODULES


def check_requirements():
    """
    Ensures all requirements for SlicerFlywheelConnect are installed.

    NOTE: Updating pip is bad practice inside modules
    NOTE: Updating existing modules inside Slicer is considered bad practice
    """
    for spec in REQUIRED_MODULES:
        if not importlib.util.find_spec(spec):
            pip_install(f"{spec}") 
