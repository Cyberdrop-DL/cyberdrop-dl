#!/bin/sh
if command -v pip >/dev/null 2>&1; then
    pip uninstall cyberdrop-dl
    pip uninstall cyberdrop-dl-patched
fi
uv tool uninstall cyberdrop-dl-patched
uv cache clean
