#!/bin/sh
pip uninstall cyberdrop-dl
pip uninstall cyberdrop-dl-patched
uv tool uninstall cyberdrop-dl-patched
uv cache clean
