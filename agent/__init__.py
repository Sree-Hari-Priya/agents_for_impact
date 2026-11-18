import sys
import os

_local_pkg = "/config/.local_packages"
if os.path.exists(_local_pkg) and _local_pkg not in sys.path:
    sys.path.insert(0, _local_pkg)

from . import agent as agent
from .agent import root_agent

__all__ = ["agent", "root_agent"]
