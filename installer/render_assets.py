#!/usr/bin/env python3
"""Render installer icons from the committed PNG (build-time only, Pillow — no Cairo)."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_PNG = ROOT / 'installer' / 'windows' / 'spickfolio.png'


def _open_source():
    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit('Install build deps: pip install -r requirements-packaging.txt') from exc
    if not SOURCE_PNG.is_file():
        raise SystemExit(f'Missing source icon: {SOURCE_PNG}')
    return Image.open(SOURCE_PNG)


def render_png(out_path: Path, size: int = 256) -> None:
    from PIL import Image

    image = _open_source().convert('RGBA')
    image = image.resize((size, size), Image.Resampling.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, format='PNG')


def render_ico(out_path: Path) -> None:
    image = _open_source().convert('RGBA')
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
