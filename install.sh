#!/bin/bash

# =====================================================================
# Image-Tea Installation Script for Unix-like Systems
# Author: Mudrikul Hikam
# Last Updated: January, 1 2026
# 
# This script performs Python environment setup and dependency installation
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
        else
            PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE_TAG}/cpython-${PYTHON_VERSION}+${RELEASE_TAG}-aarch64-unknown-linux-gnu-install_only.tar.gz"
        fi
        ;;
    Darwin*)
        OS_DIR="MacOS"
        INSTALL_DIR="python/${OS_DIR}"
        
        # Detect macOS version
        MACOS_VERSION=$(sw_vers -productVersion)
        MACOS_MAJOR=$(echo "${MACOS_VERSION}" | cut -d '.' -f 1)
        MACOS_MINOR=$(echo "${MACOS_VERSION}" | cut -d '.' -f 2)
        
        # Use Python 3.8 for older macOS versions (< 10.14)
        if [ "${MACOS_MAJOR}" -lt 11 ] && [ "${MACOS_MINOR}" -lt 14 ]; then
            echo "Detected older macOS version ${MACOS_VERSION}. Using Python 3.8 for compatibility..."
            PYTHON_VERSION="3.8.19"
            RELEASE_TAG="20240726"
            PYTHON_PATH="${BASE_DIR}/${INSTALL_DIR}/bin/python3.8"
        fi
        
        if [ "${ARCH}" = "x86_64" ]; then
            PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE_TAG}/cpython-${PYTHON_VERSION}+${RELEASE_TAG}-x86_64-apple-darwin-install_only.tar.gz"
        else
            PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE_TAG}/cpython-${PYTHON_VERSION}+${RELEASE_TAG}-aarch64-apple-darwin-install_only.tar.gz"
        fi
        
        # Detect Homebrew prefix and set library paths for macOS
        if [ -x "/opt/homebrew/bin/brew" ]; then
            BREW_PREFIX="/opt/homebrew"
        elif [ -x "/usr/local/bin/brew" ]; then
            BREW_PREFIX="/usr/local"
        else
            BREW_PREFIX=""
        fi
        
        if [ -n "${BREW_PREFIX}" ]; then
            export PATH="${BREW_PREFIX}/bin:${BREW_PREFIX}/sbin:${PATH}"
            export DYLD_LIBRARY_PATH="${BREW_PREFIX}/lib:${DYLD_LIBRARY_PATH}"
            export DYLD_FRAMEWORK_PATH="${BREW_PREFIX}/lib:${DYLD_FRAMEWORK_PATH}"
        fi
        ;;
    *)
        echo "Unsupported operating system: ${OS}"
        exit 1
        ;;
esac

# Set Python path based on detected configuration
if [ "${PYTHON_VERSION}" = "3.8.19" ]; then
    PYTHON_PATH="${BASE_DIR}/${INSTALL_DIR}/bin/python3.8"
else
    PYTHON_PATH="${BASE_DIR}/${INSTALL_DIR}/bin/python3.12"
fi
REQUIREMENTS_FILE="${BASE_DIR}/requirements.txt"
TEMP_DIR="${BASE_DIR}/temp"
VERIFY_FILE="${TEMP_DIR}/.is_installation_verified"

# =====================================================================
#######################################################################
# Check for compiler (required for some Python packages)
#######################################################################
echo "Checking system requirements..."
echo ""

if [ "${OS}" = "Linux" ]; then
    if ! command -v clang &> /dev/null && ! command -v gcc &> /dev/null; then
        echo "==================================================="
        echo "  C compiler (clang or gcc) is required."
        echo "  Installing build-essential package..."
        echo "  You may be asked for your password."
        echo "==================================================="
        sudo apt-get update && sudo apt-get install -y build-essential clang
    else
        echo "[OK] C compiler found."
    fi
elif [ "${OS}" = "Darwin" ]; then
    if ! command -v clang &> /dev/null; then
        echo "==================================================="
        echo "  Xcode Command Line Tools required for macOS."
        echo "  Installing now..."
        echo "==================================================="
        xcode-select --install
        echo "Please complete the installation dialog, then re-run this script."
        exit 0
    else
        echo "[OK] Xcode Command Line Tools found."
    fi
fi

# =====================================================================
#######################################################################
# Check for Qt xcb platform plugin and Python package dependencies (Linux only)
#######################################################################
if [ "${OS}" = "Linux" ]; then
    echo "Checking system dependencies for Qt, CairoSVG, opencv, and pynput..."
    MISSING_PACKAGES=""
    
    # Qt xcb platform dependencies
    for pkg in libxcb-cursor0 libxkbcommon-x11-0 libxcb-xinerama0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render0 libxcb-shm0; do
        if ! dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
            MISSING_PACKAGES="$MISSING_PACKAGES $pkg"
        fi
    done
    
    # CairoSVG dependencies
    for pkg in libcairo2-dev libpango1.0-dev; do
        if ! dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
            MISSING_PACKAGES="$MISSING_PACKAGES $pkg"
        fi
    done
    
    # opencv-python dependencies
    for pkg in libgl1-mesa-glx libglib2.0-0; do
        if ! dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
            MISSING_PACKAGES="$MISSING_PACKAGES $pkg"
        fi
    done
    
    # pynput dependencies
    for pkg in python3-xlib xdotool; do
        if ! dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
            MISSING_PACKAGES="$MISSING_PACKAGES $pkg"
        fi
    done
    
    if [ -n "$MISSING_PACKAGES" ]; then
        echo "Installing missing system dependencies:$MISSING_PACKAGES"
        echo "You may be asked for your password."
        sudo apt-get update && sudo apt-get install -y $MISSING_PACKAGES
    else
        echo "[OK] All system dependencies are installed."
    fi
fi

# =====================================================================
#######################################################################
# Check for required tools (ghostscript, exiftool, ffmpeg)
#######################################################################
echo "Checking required image processing tools..."

if [ "${OS}" = "Linux" ]; then
    MISSING_TOOLS=""
    
    if ! command -v gs &> /dev/null; then
        MISSING_TOOLS="$MISSING_TOOLS ghostscript"
    fi
    
    if ! command -v exiftool &> /dev/null; then
        MISSING_TOOLS="$MISSING_TOOLS libimage-exiftool-perl"
    fi
    
    if ! command -v ffmpeg &> /dev/null; then
        MISSING_TOOLS="$MISSING_TOOLS ffmpeg"
    fi
    
    if [ -n "$MISSING_TOOLS" ]; then
        echo "Installing required tools:$MISSING_TOOLS"
        echo "You may be asked for your password."
        sudo apt-get update && sudo apt-get install -y $MISSING_TOOLS
    else
        echo "[OK] All required tools are installed."
    fi
elif [ "${OS}" = "Darwin" ]; then
    if ! command -v brew &> /dev/null; then
        echo "Homebrew not found. Installing Homebrew..."
        echo "You may be asked for your password."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        
        # Re-detect Homebrew prefix after installation
        if [ -x "/opt/homebrew/bin/brew" ]; then
            BREW_PREFIX="/opt/homebrew"
        elif [ -x "/usr/local/bin/brew" ]; then
            BREW_PREFIX="/usr/local"
        fi
        if [ -n "${BREW_PREFIX}" ]; then
            export PATH="${BREW_PREFIX}/bin:${BREW_PREFIX}/sbin:${PATH}"
        fi
    fi
    
    MISSING_TOOLS=""
    
    if ! command -v gs &> /dev/null; then
        MISSING_TOOLS="$MISSING_TOOLS ghostscript"
    fi
    
    if ! command -v exiftool &> /dev/null; then
        MISSING_TOOLS="$MISSING_TOOLS exiftool"
    fi
    
    if ! command -v ffmpeg &> /dev/null; then
        MISSING_TOOLS="$MISSING_TOOLS ffmpeg"
    fi
    
    if ! brew list inih &> /dev/null; then
        MISSING_TOOLS="$MISSING_TOOLS inih"
    fi
    
    if ! brew list brotli &> /dev/null; then
        MISSING_TOOLS="$MISSING_TOOLS brotli"
    fi
    
    if ! brew list exiv2 &> /dev/null; then
        MISSING_TOOLS="$MISSING_TOOLS exiv2"
    fi
    
    if ! brew list cairo &> /dev/null; then
        MISSING_TOOLS="$MISSING_TOOLS cairo"
    fi
    
    if ! brew list pango &> /dev/null; then
        MISSING_TOOLS="$MISSING_TOOLS pango"
    fi
    
    if [ -n "$MISSING_TOOLS" ]; then
        echo "Installing required tools via Homebrew:$MISSING_TOOLS"
        brew install $MISSING_TOOLS
    else
        echo "[OK] All required tools are installed."
    fi
    
    # Update library paths with Homebrew prefix
    if command -v brew &> /dev/null; then
        BREW_PREFIX="$(brew --prefix)"
        export DYLD_LIBRARY_PATH="${BREW_PREFIX}/lib:${DYLD_LIBRARY_PATH}"
        export DYLD_FRAMEWORK_PATH="${BREW_PREFIX}/lib:${DYLD_FRAMEWORK_PATH}"
    fi
fi

echo ""
echo "System requirements check complete."

# =====================================================================
# Main installation loop with verification
# =====================================================================
install_python() {
    echo ""
    echo "====================================="
    echo " Starting Python installation..."
    echo "====================================="
    echo ""
    
    # Check if Python directory exists
    if [ -d "${BASE_DIR}/${INSTALL_DIR}" ]; then
        echo "Python installation found. Installing requirements..."
        if [ -f "${REQUIREMENTS_FILE}" ]; then
            "${PYTHON_PATH}" -m pip install -r "${REQUIREMENTS_FILE}" --no-warn-script-location
        else
            echo "Warning: requirements.txt not found. Skipping package installation."
        fi
        return 0
    fi
    
    # =====================================================================
    # Define variables for setup process
    # =====================================================================
    PYTHON_ARCHIVE="/tmp/python-${PYTHON_VERSION}.tar.gz"
    
    # =====================================================================
    # Create Python directory
    # =====================================================================
    echo "Creating Python directory..."
    mkdir -p "${BASE_DIR}/${INSTALL_DIR}"
    
    # =====================================================================
    # Download and extract Python standalone distribution
    # =====================================================================
    echo "Downloading Python standalone distribution..."
    if command -v curl &> /dev/null; then
        curl -L "${PYTHON_URL}" -o "${PYTHON_ARCHIVE}" || { echo "curl download failed"; exit 1; }
    elif command -v wget &> /dev/null; then
        wget "${PYTHON_URL}" -O "${PYTHON_ARCHIVE}" || { echo "wget download failed"; exit 1; }
    else
        echo "Error: Neither curl nor wget is available. Cannot download Python."
        exit 1
    fi
    
    # Verify the downloaded file exists and has content
    if [ ! -s "${PYTHON_ARCHIVE}" ]; then
        echo "Downloaded Python archive is empty or does not exist."
        exit 1
    fi
    
    echo "Extracting Python..."
    # Create a temporary directory for safer extraction
    TEMP_EXTRACT_DIR="/tmp/python-extract-$$"
    mkdir -p "${TEMP_EXTRACT_DIR}"
    
    # Extract with error handling and progress feedback
    echo "Extracting to temporary location first..."
    tar -xzf "${PYTHON_ARCHIVE}" -C "${TEMP_EXTRACT_DIR}" || {
        echo "Extraction failed. The archive may be corrupted or incompatible."
        echo "Technical details:"
        file "${PYTHON_ARCHIVE}"
        du -sh "${PYTHON_ARCHIVE}"
        rm -rf "${TEMP_EXTRACT_DIR}"
        exit 1
    }
    
    # Move files to final location
    echo "Moving files to installation directory..."
    if [ -d "${TEMP_EXTRACT_DIR}/python" ]; then
        echo "Extracting from nested python directory structure..."
        cp -r "${TEMP_EXTRACT_DIR}/python"/* "${BASE_DIR}/${INSTALL_DIR}/" || {
            echo "Failed to copy extracted files to installation directory."
            exit 1
        }
    else
        cp -r "${TEMP_EXTRACT_DIR}"/* "${BASE_DIR}/${INSTALL_DIR}/" || {
            echo "Failed to copy extracted files to installation directory."
            exit 1
        }
    fi
    
    # Clean up temporary files
    rm -rf "${TEMP_EXTRACT_DIR}"
    rm -f "${PYTHON_ARCHIVE}"
    
    # Verify Python executable exists after extraction
    if [ ! -f "${PYTHON_PATH}" ]; then
        echo "Python executable not found after extraction. Installation failed."
        echo "Expected path: ${PYTHON_PATH}"
        echo "Files in installation directory:"
        ls -la "${BASE_DIR}/${INSTALL_DIR}"
        exit 1
    fi
    
    echo "Python extraction completed successfully."

    # Quick runtime test to ensure bundled Python works on this macOS
    echo "Testing extracted Python for runtime compatibility..."
    TEST_ERR_FILE="/tmp/python_test_err.txt"
    set +e
    "${PYTHON_PATH}" -c "import sys; print(sys.version)" 2> "${TEST_ERR_FILE}"
    PY_EXIT=$?
    set -e
    if [ ${PY_EXIT} -ne 0 ]; then
        echo "Bundled Python failed to start (exit ${PY_EXIT}). Checking error output..."
        if grep -qi "dyld: Symbol not found" "${TEST_ERR_FILE}" || grep -qi "Abort trap" "${TEST_ERR_FILE}"; then
            echo "Detected dyld symbol error or abort — this bundled Python is incompatible with the current macOS." 
            echo "Attempting to find an alternative Python on the system (python3, python3.12, Homebrew)..."
            # Prefer python3.12 if available, then python3 from PATH
            SYS_PYTHON=""
            if command -v python3.12 &> /dev/null; then
                SYS_PYTHON=$(command -v python3.12)
            elif command -v python3 &> /dev/null; then
                SYS_PYTHON=$(command -v python3)
            fi
            if [ -n "${SYS_PYTHON}" ]; then
                echo "Found system Python at ${SYS_PYTHON}. Verifying..."
                set +e
                ${SYS_PYTHON} -c "import sys; print(sys.version)" 2> "${TEST_ERR_FILE}"
                SYS_EXIT=$?
                set -e
                if [ ${SYS_EXIT} -eq 0 ]; then
                    echo "System Python works. Will use ${SYS_PYTHON} for installing pip and requirements."
                    PYTHON_PATH="${SYS_PYTHON}"
                else
                    echo "System Python found but failed to run properly. See ${TEST_ERR_FILE}" 
                    echo "Please install Python 3.12 via python.org installer or upgrade macOS, then re-run the installer." 
                    cat "${TEST_ERR_FILE}"
                    exit 1
                fi
            else
                echo "No usable system Python found. Please install Python 3.12 from https://www.python.org/downloads/mac-osx/ or upgrade macOS to a supported version." 
                echo "Error details from bundled Python:"
                cat "${TEST_ERR_FILE}"
                exit 1
            fi
        else
            echo "Bundled Python failed for an unknown reason. See details:" 
            cat "${TEST_ERR_FILE}"
            exit 1
        fi
    else
        echo "Bundled Python appears to run normally." 
    fi
    rm -f "${TEST_ERR_FILE}"

    # =====================================================================
    # Set up pip in the Python distribution
    # =====================================================================
    echo "Setting up pip..."
    
    if [ ! -f "${REQUIREMENTS_FILE}" ]; then
        echo "Creating empty requirements.txt file..."
        touch "${REQUIREMENTS_FILE}"
    fi
    
    # Download get-pip.py and install pip
    echo "Installing pip..."
    PIP_TEMP="/tmp/get-pip.py"
    if command -v curl &> /dev/null; then
        curl -L "https://bootstrap.pypa.io/get-pip.py" -o "${PIP_TEMP}" || {
            echo "Failed to download get-pip.py"
            exit 1
        }
    elif command -v wget &> /dev/null; then
        wget "https://bootstrap.pypa.io/get-pip.py" -O "${PIP_TEMP}" || {
            echo "Failed to download get-pip.py"
            exit 1
        }
    else
        echo "Error: Neither curl nor wget is available. Cannot download pip."
        exit 1
    fi
    
    "${PYTHON_PATH}" "${PIP_TEMP}" --no-warn-script-location
    rm -f "${PIP_TEMP}"
    
    if ! "${PYTHON_PATH}" -m pip --version; then
        echo "Failed to install pip. Installation cannot continue."
        exit 1
    fi
    
    echo "Upgrading pip to the latest version..."
    "${PYTHON_PATH}" -m pip install --upgrade pip --no-warn-script-location
    
    if [ -f "${REQUIREMENTS_FILE}" ]; then
        echo "Installing required packages from requirements.txt..."
        
        # Special handling for macOS PySide6 installation
        if [ "${OS}" = "Darwin" ]; then
            echo "Installing PySide6 with additional macOS dependencies..."
            "${PYTHON_PATH}" -m pip install wheel setuptools --upgrade --no-warn-script-location
            
            if ! "${PYTHON_PATH}" -m pip install PySide6 --no-warn-script-location; then
                echo "Direct PySide6 installation failed, trying with extra options..."
                "${PYTHON_PATH}" -m pip install PySide6 --no-binary PySide6 --no-warn-script-location || {
                    echo "PySide6 installation failed. Please install macOS command line tools with 'xcode-select --install'"
                    echo "Then run this script again."
                    exit 1
                }
            fi
            
            grep -v "PySide6" "${REQUIREMENTS_FILE}" > /tmp/other_requirements.txt
            if [ -s /tmp/other_requirements.txt ]; then
                "${PYTHON_PATH}" -m pip install -r /tmp/other_requirements.txt --no-warn-script-location
            fi
            rm /tmp/other_requirements.txt
        else
            "${PYTHON_PATH}" -m pip install -r "${REQUIREMENTS_FILE}" --no-warn-script-location
        fi
    else
        echo "Warning: requirements.txt not found. Skipping package installation."
    fi
}

# =====================================================================
# Verification loop
# =====================================================================
while true; do
    install_python
    
    echo ""
    echo "================================"
    echo "Verifying Python and pip version:"
    echo "================================"
    
    if ! "${PYTHON_PATH}" --version; then
        if [ -f "${VERIFY_FILE}" ]; then
            rm -f "${VERIFY_FILE}"
        fi
        echo "Python not working. Reinstalling..."
        rm -rf "${BASE_DIR}/${INSTALL_DIR}"
        continue
    fi
    
    if ! "${PYTHON_PATH}" -c "import sys; print('Python executable:', sys.executable)"; then
        if [ -f "${VERIFY_FILE}" ]; then
            rm -f "${VERIFY_FILE}"
        fi
        echo "Python not working. Reinstalling..."
        rm -rf "${BASE_DIR}/${INSTALL_DIR}"
        continue
    fi
    
    if ! "${PYTHON_PATH}" -m pip --version; then
        if [ -f "${VERIFY_FILE}" ]; then
            rm -f "${VERIFY_FILE}"
        fi
        echo "Pip not working. Reinstalling..."
        rm -rf "${BASE_DIR}/${INSTALL_DIR}"
        continue
    fi
    
    echo ""
    echo "================================"
    echo "Verifying installed requirements:"
    echo "================================"
    REQ_MISSING=0
    
    if [ -f "${REQUIREMENTS_FILE}" ]; then
        "${PYTHON_PATH}" -m pip freeze > "/tmp/pip_freeze.txt"
        while IFS= read -r REQ; do
            if [ -n "$REQ" ] && [ "${REQ:0:1}" != "#" ]; then
                PKG_NAME=$(echo "$REQ" | sed 's/[><=~!].*//')
                if grep -qi "^${PKG_NAME}==" "/tmp/pip_freeze.txt"; then
                    echo "  [OK] $REQ"
                else
                    echo "  [MISSING/DIFFERENT] $REQ"
                    REQ_MISSING=1
                fi
            fi
        done < "${REQUIREMENTS_FILE}"
        rm -f "/tmp/pip_freeze.txt"
    else
        echo "requirements.txt not found, skipping requirements verification."
    fi
    
    if [ "${REQ_MISSING}" -eq 1 ]; then
        if [ -f "${VERIFY_FILE}" ]; then
            rm -f "${VERIFY_FILE}"
        fi
        echo "One or more dependencies are missing or incorrect. Reinstalling..."
        rm -rf "${BASE_DIR}/${INSTALL_DIR}"
        continue
    fi
    
    # All checks passed
    break
done

echo ""
echo "Setup complete."

mkdir -p "${TEMP_DIR}"
echo "ok" > "${VERIFY_FILE}"

echo ""
