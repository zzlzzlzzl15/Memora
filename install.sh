#!/bin/bash

# Memora Knowledge Graph v2.0.0 - Installation Script
# This script installs the knowledge graph visualization component

set -e

VERSION="2.0.0"
REPO_URL="https://github.com/zzlzzlzzl15/memora-knowledge-graph.git"
INSTALL_DIR="${HOME}/memora-knowledge-graph"

echo "🚀 Installing Memora Knowledge Graph v${VERSION}..."
echo ""

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Git is not installed. Please install git first."
    exit 1
fi

# Clone or update repository
if [ -d "${INSTALL_DIR}" ]; then
    echo " Updating existing installation..."
    cd "${INSTALL_DIR}"
    git pull origin main
else
    echo "📦 Cloning repository..."
    git clone "${REPO_URL}" "${INSTALL_DIR}"
    cd "${INSTALL_DIR}"
fi

# Set environment variable
echo ""
echo "️  Setting up environment..."
echo "Please add the following line to your ~/.bashrc or ~/.zshrc:"
echo ""
echo "  export KB_API_BASE=http://127.0.0.1:8080"
echo ""

read -p "Would you like to add this to your shell profile now? (y/n): " answer
if [[ $answer == "y" || $answer == "Y" ]]; then
    echo "export KB_API_BASE=http://127.0.0.1:8080" >> "${HOME}/.${SHELL##*/}rc"
    echo "✅ Environment variable added!"
    echo "   Please restart your terminal or run: source ~/.${SHELL##*/}rc"
fi

# Install dependencies (if any)
echo ""
echo "📦 Checking dependencies..."
if [ -f "package.json" ] && command -v npm &> /dev/null; then
    read -p "Would you like to install npm dependencies? (y/n): " answer
    if [[ $answer == "y" || $answer == "Y" ]]; then
        npm install
    fi
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "📖 Next steps:"
echo "   1. Make sure Memora backend is running on http://127.0.0.1:8080"
echo "   2. Open static/index.html in your browser"
echo "   3. Or start a local server: npm start"
echo ""
echo "🔗 Repository: ${REPO_URL}"
echo "📄 Documentation: https://github.com/zzlzzlzzl15/memora-knowledge-graph#readme"
echo ""
