#!/bin/bash

# =====================================================================
# Image-Tea Update Worker Script for Unix-like Systems
# Author: Mudrikul Hikam
# Last Updated: January, 1 2026
# 
# This script performs the following tasks:
# 1. Fetches the latest release from GitHub
# 2. Downloads the release ZIP file
# 3. Extracts and replaces files
# 4. Cleans up temporary files
# 5. Optionally launches the application
# =====================================================================

# =====================================================================
# The MIT License (MIT)
#
# Copyright (c) 2025 Mudrikul Hikam, Desainia Studio
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# =====================================================================

# Set base directory to the location of this script
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

RELEASES_API="https://api.github.com/repos/mudrikam/Image-Tea-nano/releases/latest"
ZIP_NAME="Image-Tea-nano.zip"
ZIP_PATH="${BASE_DIR}/temp/${ZIP_NAME}"
EXTRACT_PATH="${BASE_DIR}/temp/Image-Tea-nano-latest"
SELF="$(basename "$0")"

# Detect OS for launcher path
OS="$(uname -s)"
case "${OS}" in
    Linux*)
        LAUNCHER_PATH="${BASE_DIR}/Launcher.sh"
        ;;
    Darwin*)
        LAUNCHER_PATH="${BASE_DIR}/Launcher.sh"
        ;;
    *)
        echo "Unsupported operating system: ${OS}"
        exit 1
        ;;
esac

echo "Fetching latest release tag from GitHub..."

# Fetch latest tag using curl or wget
if command -v curl &> /dev/null; then
    TAG_NAME=$(curl -s "$RELEASES_API" | grep '"tag_name":' | sed -E 's/.*"tag_name": "([^"]+)".*/\1/')
elif command -v wget &> /dev/null; then
    TAG_NAME=$(wget -qO- "$RELEASES_API" | grep '"tag_name":' | sed -E 's/.*"tag_name": "([^"]+)".*/\1/')
else
    echo "Error: Neither curl nor wget is available. Cannot fetch release information."
    exit 1
fi

if [ -z "$TAG_NAME" ]; then
    echo "Failed to fetch release tag. Using fallback version v1.0.42"
    TAG_NAME="v1.0.42"
fi

echo "TAG obtained: [$TAG_NAME]"

REPO_URL="https://github.com/mudrikam/Image-Tea-nano/releases/download/${TAG_NAME}/${ZIP_NAME}"

echo ""
echo "============================================"
echo "Downloading file:"
echo "  Source : $REPO_URL"
echo "  Target : $ZIP_PATH"
echo "============================================"

echo "Downloading latest release ZIP from GitHub..."

if command -v curl &> /dev/null; then
    curl -L "$REPO_URL" -o "$ZIP_PATH" || {
        echo "Failed to download ZIP file. Aborting update."
        exit 1
    }
elif command -v wget &> /dev/null; then
    wget "$REPO_URL" -O "$ZIP_PATH" || {
        echo "Failed to download ZIP file. Aborting update."
        exit 1
    }
fi

if [ ! -f "$ZIP_PATH" ]; then
    echo "Failed to download ZIP file. Aborting update."
    exit 1
fi

echo ""
echo "============================================"
echo "Extracting ZIP:"
echo "  Source : $ZIP_PATH"
echo "  Target : $EXTRACT_PATH"
echo "============================================"

# Clean up previous extraction
rm -rf "$EXTRACT_PATH"

# Extract ZIP
unzip -q "$ZIP_PATH" -d "$EXTRACT_PATH" || {
    echo "Extraction failed. Aborting update."
    rm -f "$ZIP_PATH"
    exit 1
}

# Find extracted root directory
EXTRACTED_ROOT=$(find "$EXTRACT_PATH" -maxdepth 1 -type d ! -path "$EXTRACT_PATH" | head -n 1)

if [ -z "$EXTRACTED_ROOT" ]; then
    echo "Extraction failed. Aborting update."
    rm -f "$ZIP_PATH"
    exit 1
fi

echo ""
echo "============================================"
echo "Replacing files with latest version"
echo "============================================"

# Copy all files except this script
cd "$EXTRACTED_ROOT"
find . -type f | while read -r file; do
    SRC="$EXTRACTED_ROOT/$file"
    DST="$BASE_DIR/$file"
    
    # Skip this script itself
    if [ "$(basename "$DST")" = "$SELF" ]; then
        continue
    fi
    
    # Create directory if it doesn't exist
    mkdir -p "$(dirname "$DST")"
    
    # Copy file
    cp -f "$SRC" "$DST" 2>/dev/null
done

echo ""
echo "============================================"
echo "Cleaning up temporary files:"
echo "  Deleting : $ZIP_PATH"
echo "  Deleting : $EXTRACT_PATH"
echo "============================================"

rm -f "$ZIP_PATH"
rm -rf "$EXTRACT_PATH"

echo ""
echo "================================"
echo "Update finished."
echo "================================"
echo ""
echo "Relaunching Image-Tea..."

if [ -f "$LAUNCHER_PATH" ]; then
    chmod +x "$LAUNCHER_PATH"
    # Self-delete before relaunching
    rm -f "$0"
    exec "$LAUNCHER_PATH"
else
    echo "Launcher not found at: $LAUNCHER_PATH"
    # Self-delete
    rm -f "$0"
    exit 1
fi
