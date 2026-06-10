#!/bin/bash
# Build Linux installers: standalone binary, AppImage, and .deb (no Python required at runtime).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="$(tr -d '[:space:]' < VERSION)"
DIST="$ROOT/dist"
BUILD="$ROOT/build"
APPDIR="$BUILD/spickFolio.AppDir"

echo "==> spickFolio $VERSION — Linux installer build"

python3 -m pip install -q -r requirements-packaging.txt
python3 installer/render_assets.py --png "$BUILD/icon.png"

echo "==> PyInstaller bundle"
pyinstaller --noconfirm spickfolio.spec
BINARY="$DIST/spickFolio"
if [ ! -f "$BINARY" ]; then
    echo "Expected binary at $BINARY" >&2
    exit 1
fi
chmod +x "$BINARY"

echo "==> AppImage"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
cp "$BINARY" "$APPDIR/usr/bin/spickFolio"
cp "$BUILD/icon.png" "$APPDIR/spickfolio.png"
cp installer/linux/spickfolio.appdir.desktop "$APPDIR/spickfolio.desktop"
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0" 2>/dev/null || realpath "$0")")"
exec "$HERE/usr/bin/spickFolio" "$@"
EOF
chmod +x "$APPDIR/AppRun" "$APPDIR/usr/bin/spickFolio"

download_file() {
    local url="$1"
    local dest="$2"
    if command -v wget >/dev/null 2>&1; then
        wget -q -O "$dest" "$url"
    elif command -v curl >/dev/null 2>&1; then
        curl -fsSL -o "$dest" "$url"
    else
        echo "Need wget or curl to download appimagetool" >&2
        exit 1
    fi
}

APPIMAGETOOL="$BUILD/appimagetool"
if [ ! -x "$APPIMAGETOOL" ]; then
    download_file \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" \
        "$APPIMAGETOOL"
    chmod +x "$APPIMAGETOOL"
fi
APPIMAGE_OUT="$DIST/spickFolio-${VERSION}-x86_64.AppImage"
rm -f "$APPIMAGE_OUT"
# Build hosts may lack FUSE; extract-and-run avoids needing libfuse at build time.
APPIMAGE_EXTRACT_AND_RUN=1 ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$APPIMAGE_OUT"
chmod +x "$APPIMAGE_OUT"

echo "==> Debian package"
DEB_ROOT="$BUILD/deb-root"
rm -rf "$DEB_ROOT"
mkdir -p "$DEB_ROOT/DEBIAN"
mkdir -p "$DEB_ROOT/opt/spickfolio"
mkdir -p "$DEB_ROOT/usr/share/applications"
mkdir -p "$DEB_ROOT/usr/share/icons/hicolor/256x256/apps"

cp "$BINARY" "$DEB_ROOT/opt/spickfolio/spickFolio"
chmod 755 "$DEB_ROOT/opt/spickfolio/spickFolio"
cp installer/linux/spickfolio.desktop "$DEB_ROOT/usr/share/applications/"
cp "$BUILD/icon.png" "$DEB_ROOT/usr/share/icons/hicolor/256x256/apps/spickfolio.png"

cat > "$DEB_ROOT/DEBIAN/control" <<EOF
Package: spickfolio
Version: ${VERSION}
Section: education
Priority: optional
Architecture: amd64
Maintainer: Karim-Termanini <bashirtermaniniabdulkarim@gmail.com>
Description: R/Python statistics cheat sheet and dataset browser
 Standalone statistics cheat sheets and dataset browser with Rdatasets,
 Hugging Face and Kaggle support. No Python install required.
EOF

cat > "$DEB_ROOT/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true
fi
EOF
chmod 755 "$DEB_ROOT/DEBIAN/postinst"

DEB_OUT="$DIST/spickfolio_${VERSION}_amd64.deb"
rm -f "$DEB_OUT"
if command -v dpkg-deb >/dev/null 2>&1; then
    dpkg-deb --build --root-owner-group "$DEB_ROOT" "$DEB_OUT"
else
    echo "Skipping .deb (dpkg-deb not installed; available in CI on Ubuntu)" >&2
    DEB_OUT=""
fi

echo ""
echo "Built:"
echo "  $BINARY"
echo "  $APPIMAGE_OUT"
if [ -n "$DEB_OUT" ]; then
    echo "  $DEB_OUT"
fi
