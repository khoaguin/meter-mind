import argparse
import asyncio

from edgesim.fleet import load_fleet, run_fleet


def main() -> None:
    parser = argparse.ArgumentParser(prog="edgesim")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run the virtual fleet")
    run.add_argument("--config", required=True)
    run.add_argument("--max-ticks", type=int, default=None)
    args = parser.parse_args()

    if args.cmd == "run":
        cfg = load_fleet(args.config)
        asyncio.run(run_fleet(cfg, max_ticks=args.max_ticks))


if __name__ == "__main__":
    main()
