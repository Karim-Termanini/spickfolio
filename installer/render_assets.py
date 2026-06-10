#!/usr/bin/env python3
"""Render installer icons from assets/icon.svg (build-time only)."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def render_png(out_path: Path, size: int = 256) -> None:
    try:
        import cairosvg
    except ImportError as exc:
        raise SystemExit('Install build deps: pip install -r requirements-packaging.txt') from exc
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cairosvg.svg2png(
        url=str(ROOT / 'assets' / 'icon.svg'),
        write_to=str(out_path),
        output_width=size,
        output_height=size,
    )


def render_ico(out_path: Path) -> None:
    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit('Install build deps: pip install -r requirements-packaging.txt') from exc
    png_path = out_path.with_suffix('.png')
    if not png_path.is_file():
        render_png(png_path)
    image = Image.open(png_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(
        out_path,
        format='ICO',
        sizes=[(256, 256), (48, 48), (32, 32), (16, 16)],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--png', type=Path, default=ROOT / 'build' / 'icon.png')
    parser.add_argument('--ico', type=Path, default=ROOT / 'installer' / 'windows' / 'spickfolio.ico')
    args = parser.parse_args()
    render_png(args.png)
    render_ico(args.ico)
    print(f'Wrote {args.png}')
    print(f'Wrote {args.ico}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
