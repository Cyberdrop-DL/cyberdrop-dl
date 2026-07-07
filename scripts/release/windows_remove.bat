@echo off
where pip >nul 2>&1
if %errorlevel%==0 (
    pip uninstall cyberdrop-dl
    pip uninstall cyberdrop-dl-patched
)
uv tool uninstall cyberdrop-dl-patched
uv cache clean
pause
