import importlib.metadata

try:
	__version__ = importlib.metadata.version("cyberdrop-dl-patched")
except importlib.metadata.PackageNotFoundError:
	# Running from source (not installed). Use a local fallback version so runtime
	# imports don't fail during development or CI when the package metadata is
	# not available.
	__version__ = "0+local"
