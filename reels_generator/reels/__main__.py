"""CLI entrypoint: ``python -m reels <command>``.

Commands:
    run        Generate and stitch Reels for every hook in the configured source.
    generate   Only generate hook videos via HeyGen (no stitching).
    stitch     Only stitch an existing hook mp4 to the core video.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import Settings
from .hooks_source import read_csv_hooks, read_google_sheet_hooks
from .pipeline import run_pipeline
from .stitcher import StitchSpec, stitch


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _load_hooks(args: argparse.Namespace, settings: Settings):
    if args.sheet_id:
        return read_google_sheet_hooks(
            args.sheet_id, args.sheet_range, args.service_account
        )
    return read_csv_hooks(args.hooks_csv or settings.hooks_csv_path)


def cmd_run(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    hooks = _load_hooks(args, settings)
    if not hooks:
        print("no hooks found", file=sys.stderr)
        return 2
    results = run_pipeline(hooks, settings)
    ok = sum(1 for r in results if r.ok)
    print(f"\nFinished {ok}/{len(results)} reels")
    for r in results:
        if r.ok:
            print(f"  ok  #{r.hook.index}: {r.final_path}")
        else:
            print(f"  ERR #{r.hook.index}: {r.error}")
    return 0 if ok == len(results) else 1


def cmd_stitch(args: argparse.Namespace) -> int:
    stitch(
        StitchSpec(
            hook_path=Path(args.hook),
            core_path=Path(args.core),
            output_path=Path(args.output),
            width=args.width,
            height=args.height,
        )
    )
    print(f"wrote {args.output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reels")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Full pipeline: generate + stitch")
    run_p.add_argument("--hooks-csv", type=Path, help="Path to a hooks CSV")
    run_p.add_argument("--sheet-id", help="Google Sheet ID to read hooks from")
    run_p.add_argument("--sheet-range", default="A:A", help="A1 range")
    run_p.add_argument("--service-account", help="Path to GCP service account JSON")
    run_p.set_defaults(func=cmd_run)

    stitch_p = sub.add_parser("stitch", help="Stitch one hook to the core video")
    stitch_p.add_argument("--hook", required=True)
    stitch_p.add_argument("--core", required=True)
    stitch_p.add_argument("--output", required=True)
    stitch_p.add_argument("--width", type=int, default=1080)
    stitch_p.add_argument("--height", type=int, default=1920)
    stitch_p.set_defaults(func=cmd_stitch)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
