#!/bin/sh
# Ignore any test that makes a real HTTP request
uv run pytest -m "not crawler_test_case and not http" -v
