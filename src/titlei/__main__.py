"""Allow ``python -m titlei`` as well as the ``titlei`` console script.

This is the escape hatch when the virtual environment is not activated:
``.venv/bin/python -m titlei verify`` works from anywhere, with no PATH changes.
"""

from titlei.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
