from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="インフルとの死闘")
    parser.add_argument("--smoke-test", action="store_true",
                        help="配布物の初期化・データ保存を検査して終了（通しプレイではない）")
    parser.add_argument("--smoke-output", type=Path, help="検査結果JSONの出力先")
    args = parser.parse_args(argv)
    if args.smoke_test:
        if args.smoke_output is None:
            parser.error("--smoke-test requires --smoke-output")
        from src.core.packaged_smoke import run_smoke_test
        return run_smoke_test(args.smoke_output)
    if args.smoke_output is not None:
        parser.error("--smoke-output requires --smoke-test")
    from src.core.game import Game
    Game().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
