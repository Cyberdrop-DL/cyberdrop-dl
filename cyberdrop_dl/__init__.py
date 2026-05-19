import importlib.metadata
import sys

_ = sys.path.pop(0)

__dist_name__ = "cyberdrop-dl-patched"
__version__ = importlib.metadata.version(__dist_name__)
