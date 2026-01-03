#!/bin/bash

# =====================================================================
# Image-Tea Launcher Script for Unix-like Systems
# Author: Mudrikul Hikam
# Last Updated: Januari, 3 2026
# 
# This script performs the following tasks:
# 1. If Python folder exists, directly runs main.py
# 2. If Python folder doesn't exist:
#    - Downloads Python 3.12.10 standalone distribution for the OS
#    - Sets up pip in the distribution
#    - Installs required packages from requirements.txt
#    - Runs main.py
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

# =====================================================================
# Determine OS and configure environment variables
# =====================================================================
PYTHON_VERSION="3.12.10"
RELEASE_TAG="20250409"
OS="$(uname -s)"
ARCH="$(uname -m)"

# Normalize architecture names
case "${ARCH}" in
    x86_64|amd64)
        ARCH="x86_64"
        ;;
    aarch64|arm64)
        ARCH="aarch64"
        ;;
    *)
        echo "Unsupported architecture: ${ARCH}"
        exit 1
        ;;
esac

case "${OS}" in
    Linux*)
        OS_DIR="Linux"
        INSTALL_DIR="python/${OS_DIR}"
        if [ "${ARCH}" = "x86_64" ]; then
            PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE_TAG}/cpython-${PYTHON_VERSION}+${RELEASE_TAG}-x86_64-unknown-linux-gnu-install_only.tar.gz"
            export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/usr/lib:${LD_LIBRARY_PATH}"
        else
            PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE_TAG}/cpython-${PYTHON_VERSION}+${RELEASE_TAG}-aarch64-unknown-linux-gnu-install_only.tar.gz"
            export LD_LIBRARY_PATH="/usr/lib/aarch64-linux-gnu:/usr/lib:${LD_LIBRARY_PATH}"
        fi
        export XDG_RUNTIME_DIR="/run/user/$(id -u)"
        export QT_QPA_PLATFORM=xcb
        ;;
    Darwin*)
        OS_DIR="MacOS"
        INSTALL_DIR="python/${OS_DIR}"
        
        # Detect macOS version
        MACOS_VERSION=$(sw_vers -productVersion)
        MACOS_MAJOR=$(echo "${MACOS_VERSION}" | cut -d '.' -f 1)
        MACOS_MINOR=$(echo "${MACOS_VERSION}" | cut -d '.' -f 2)
        
        # Use Python 3.9 for older macOS versions (< 10.14)
        if [ "${MACOS_MAJOR}" -lt 11 ] && [ "${MACOS_MINOR}" -lt 14 ]; then
            echo "Detected older macOS version ${MACOS_VERSION}. Using Python 3.9 for compatibility..."
            PYTHON_VERSION="3.9.20"
            RELEASE_TAG="20240726"
            PYTHON_PATH="${BASE_DIR}/${INSTALL_DIR}/bin/python3.9"
        fi
        
        if [ "${ARCH}" = "x86_64" ]; then
            PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE_TAG}/cpython-${PYTHON_VERSION}+${RELEASE_TAG}-x86_64-apple-darwin-install_only.tar.gz"
        else
            PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE_TAG}/cpython-${PYTHON_VERSION}+${RELEASE_TAG}-aarch64-apple-darwin-install_only.tar.gz"
        fi
        export QT_MAC_WANTS_LAYER=1
        
        # Detect Homebrew prefix (Apple Silicon vs Intel)
        if [ -x "/opt/homebrew/bin/brew" ]; then
            BREW_PREFIX="/opt/homebrew"
        elif [ -x "/usr/local/bin/brew" ]; then
            BREW_PREFIX="/usr/local"
        else
            BREW_PREFIX=""
        fi
        
        # Add Homebrew to PATH if not already there
        if [ -n "${BREW_PREFIX}" ] && [[ ":$PATH:" != *":${BREW_PREFIX}/bin:"* ]]; then
            export PATH="${BREW_PREFIX}/bin:${BREW_PREFIX}/sbin:${PATH}"
        fi
        
        export DYLD_FRAMEWORK_PATH="${BASE_DIR}/${INSTALL_DIR}/lib:${DYLD_FRAMEWORK_PATH}"
        export DYLD_LIBRARY_PATH="${BASE_DIR}/${INSTALL_DIR}/lib:${DYLD_LIBRARY_PATH}"
        ;;
    *)
        echo "Unsupported operating system: ${OS}"
        exit 1
        ;;
esac

# Set Python path based on detected configuration
if [ "${PYTHON_VERSION}" = "3.9.20" ]; then
    PYTHON_PATH="${BASE_DIR}/${INSTALL_DIR}/bin/python3.9"
else
    PYTHON_PATH="${BASE_DIR}/${INSTALL_DIR}/bin/python3.12"
fi
REQUIREMENTS_FILE="${BASE_DIR}/requirements.txt"

# =====================================================================
#######################################################################
# Robust dependency check (folder, files, pip, requirements)
#######################################################################
echo ""
echo "Checking Python environment and dependencies..."
CHECK_FAILED=0
VERIFY_FILE="${BASE_DIR}/temp/.is_installation_verified"

# Check Python folder
if [ -d "${BASE_DIR}/${INSTALL_DIR}" ]; then
    echo "  [OK] python/${OS_DIR} folder found."
else
    echo "  [MISSING] python/${OS_DIR} folder not found!"
    CHECK_FAILED=1
fi

# Check python executable
if [ -f "${PYTHON_PATH}" ]; then
    PYTHON_VERSION_DISPLAY=$(basename "${PYTHON_PATH}")
    echo "  [OK] ${PYTHON_VERSION_DISPLAY} executable found."
else
    PYTHON_VERSION_DISPLAY=$(basename "${PYTHON_PATH}")
    echo "  [MISSING] ${PYTHON_VERSION_DISPLAY} executable not found!"
    CHECK_FAILED=1
fi

# Check pip module (only if python exists)
if [ "${CHECK_FAILED}" -eq 0 ]; then
    if "${PYTHON_PATH}" -m pip --version &> /dev/null; then
        echo "  [OK] pip module found."
    else
        echo "  [MISSING] pip not working!"
        CHECK_FAILED=1
    fi
fi

# Check requirements.txt
if [ -f "${REQUIREMENTS_FILE}" ]; then
    echo "  [OK] requirements.txt found."
else
    echo "  [MISSING] requirements.txt not found!"
    CHECK_FAILED=1
fi

# Check .is_installation_verified
if [ -f "${VERIFY_FILE}" ]; then
    echo "  [OK] .is_installation_verified found."
else
    echo "  [MISSING] .is_installation_verified not found!"
    CHECK_FAILED=1
fi

# Check pip dependencies (only if pip is working)
if [ "${CHECK_FAILED}" -eq 0 ]; then
    if "${PYTHON_PATH}" -m pip check &> /dev/null; then
        echo "  [OK] pip dependencies valid."
    else
        echo "  [MISSING] pip dependencies not valid!"
        CHECK_FAILED=1
    fi
fi

# Robust: Check requirements.txt vs pip freeze
if [ "${CHECK_FAILED}" -eq 0 ]; then
    "${PYTHON_PATH}" -m pip freeze > "/tmp/pip_freeze_check.txt"
    while IFS= read -r REQ; do
        # Skip empty lines and comments
        if [ -n "$REQ" ] && [ "${REQ:0:1}" != "#" ]; then
            # Extract package name (before == or >= etc)
            PKG_NAME=$(echo "$REQ" | sed 's/[><=~!].*//')
            if grep -qi "^${PKG_NAME}==" "/tmp/pip_freeze_check.txt"; then
                echo "  [OK] $REQ installed."
            else
                echo "  [MISSING] $REQ not installed!"
                CHECK_FAILED=1
            fi
        fi
    done < "${REQUIREMENTS_FILE}"
    rm -f "/tmp/pip_freeze_check.txt"
fi

# If any check failed, run install.sh for dependency recovery
if [ "${CHECK_FAILED}" -eq 1 ]; then
    echo ""
    echo "====================================="
    echo " Python environment not detected, incomplete, or broken."
    echo " Running install.sh to repair dependencies..."
    echo "====================================="
    INSTALL_SH="${BASE_DIR}/install.sh"
    if [ -f "${INSTALL_SH}" ]; then
        chmod +x "${INSTALL_SH}"
        bash "${INSTALL_SH}"
        echo ""
        echo "================================"
        echo " Dependency repair complete."
        echo " Launching Image Tea..."
        echo "================================"
    else
        echo "ERROR: install.sh not found!"
        exit 1
    fi
fi

# =====================================================================
# Launch the application
# =====================================================================
echo ""
echo "==================================================="
echo "        Image-Tea Application Launcher             "
echo "==================================================="
echo "Dependencies verified. Running main.py..."
echo ""
exec "${PYTHON_PATH}" "${BASE_DIR}/main.py"