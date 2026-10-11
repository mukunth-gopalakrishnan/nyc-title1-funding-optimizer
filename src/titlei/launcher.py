"""Entry point for the downloadable, self-contained binary.

With arguments it is exactly the ``titlei`` command line. With none -- which is
what happens when someone double-clicks the file -- it runs the guided demo,
writes the report to a folder in their home directory, opens it in their
browser, and waits for Enter so a double-clicked window does not vanish before
they have read it.
"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

from titlei import __version__
from titlei.cli import _make_output_robust
from titlei.cli import main as cli_main

OUTPUT_DIR = Path.home() / "titlei-output"


def _guided() -> int:
    from titlei.demo import run_demo

    _make_output_robust()  # the double-click path never goes through cli.main

    print(f"NYC Title I Funding Optimizer {__version__}")
    print("No arguments given, so running the guided demo.")
    print(f"Results will be written to {OUTPUT_DIR}\n")

    result = run_demo(out_dir=OUTPUT_DIR / "demo", runs_dir=OUTPUT_DIR / "runs")

    report = result.get("report")
    if report:
        print(f"\nOpening the report in your browser: {report}")
        try:
            webbrowser.open(Path(report).resolve().as_uri())
        except Exception:  # a headless machine has no browser; the path is printed
            pass

    print("\nThis program is also a full command line. From a terminal, try:")
    print("    titlei --help")
    print("    titlei verify      # prove it reproduces the published results")
    print("    titlei wizard      # build your own scenario, guided")

    if sys.stdin is not None and sys.stdin.isatty():
        try:
            input("\nPress Enter to close.")
        except EOFError:
            pass
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        return _guided()
    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
