#!/bin/bash

# One-Click Release Script for Memora Knowledge Graph v2.0.0
# Usage: ./release.sh [version] [message]
# Example: ./release.sh 2.0.0 "Preview + Fullscreen Modal Architecture"

set -e

VERSION="${1:-2.0.0}"
MESSAGE="${2:-Release v${VERSION}}"
TAG="v${VERSION}"

echo "🚀 Releasing Memora Knowledge Graph ${TAG}"
echo ""

# Validate version format
if ! [[ $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "❌ Error: Invalid version format. Use semantic versioning (e.g., 2.0.0)"
    exit 1
fi

# Check if on main branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "⚠️  Warning: You're on branch '$CURRENT_BRANCH', not 'main'"
    read -p "Continue anyway? (y/n): " answer
    if [[ $answer != "y" && $answer != "Y" ]]; then
        echo "Aborting release."
        exit 1
    fi
fi

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo "❌ Error: You have uncommitted changes"
    echo "Please commit or stash them first:"
    echo "  git add ."
    echo "  git commit -m \"your message\""
    echo "  git push origin main"
    exit 1
fi

echo "📋 Pre-release checks..."
echo ""

# Run pre-release checklist
echo "✓ Checking version numbers..."
PKG_VERSION=$(grep '"version"' package.json | cut -d'"' -f4)
FILE_VERSION=$(cat VERSION)
SKILL_VERSION=$(grep "version:" openclaw-skill/SKILL.md | head -1 | awk '{print $2}')

if [ "$PKG_VERSION" != "$VERSION" ] || [ "$FILE_VERSION" != "$VERSION" ] || [ "$SKILL_VERSION" != "$VERSION" ]; then
    echo "❌ Version mismatch!"
    echo "   package.json: $PKG_VERSION"
    echo "   VERSION file: $FILE_VERSION"
    echo "   SKILL.md:     $SKILL_VERSION"
    echo "   Expected:     $VERSION"
    echo ""
    echo "Run: ./bump_version.sh $VERSION"
    exit 1
fi
echo "  ✓ All version numbers match: $VERSION"

echo "✓ Checking required files..."
REQUIRED_FILES=(
    "static/index.html"
    "static/style.css"
    "static/script.js"
    "openclaw-skill/SKILL.md"
    "package.json"
    "README.md"
    "CHANGELOG.md"
    "LICENSE"
    "install.sh"
    ".github/workflows/release.yml"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Missing required file: $file"
        exit 1
    fi
done
echo "  ✓ All required files present"

echo "✓ Checking CHANGELOG entry..."
if ! grep -q "\[${VERSION}\]" CHANGELOG.md; then
    echo "️  Warning: No changelog entry found for v${VERSION}"
    read -p "Continue without changelog entry? (y/n): " answer
    if [[ $answer != "y" && $answer != "Y" ]]; then
        echo "Please add changelog entry and try again."
        exit 1
    fi
fi
echo "  ✓ Changelog entry exists"

echo ""
echo "✅ All pre-release checks passed!"
echo ""

# Confirm release
echo "📦 Release Summary:"
echo "   Version:  ${TAG}"
echo "   Message:  ${MESSAGE}"
echo "   Branch:   ${CURRENT_BRANCH}"
echo ""
read -p "Proceed with release? (y/n): " confirm
if [[ $confirm != "y" && $confirm != "Y" ]]; then
    echo "Release aborted."
    exit 0
fi

echo ""
echo "🔄 Starting release process..."
echo ""

# Step 1: Create tag
echo "📝 Creating git tag ${TAG}..."
git tag -a "${TAG}" -m "${MESSAGE}"
echo "  ✓ Tag created"

# Step 2: Push tag
echo "📤 Pushing tag to GitHub..."
git push origin "${TAG}"
echo "  ✓ Tag pushed"

echo ""
echo "✅ Release initiated successfully!"
echo ""
echo " What happens next:"
echo "   1. GitHub Actions workflow triggered automatically"
echo "   2. Tarball created and attached to release"
echo "   3. Release published on GitHub"
echo "   4. (Optional) Uploaded to clawhub if CLAHUB_TOKEN configured"
echo ""
echo "🔍 Monitor progress:"
echo "   https://github.com/zzlzzlzzl15/memora-knowledge-graph/actions"
echo ""
echo "📦 View release:"
echo "   https://github.com/zzlzzlzzl15/memora-knowledge-graph/releases/tag/${TAG}"
echo ""
echo "⏱️  Estimated time: 2-5 minutes"
echo ""

# Optional: Open browser to monitor
read -p "Open GitHub Actions in browser? (y/n): " open_browser
if [[ $open_browser == "y" || $open_browser == "Y" ]]; then
    if command -v open &> /dev/null; then
        open "https://github.com/zzlzzlzzl15/memora-knowledge-graph/actions"
    elif command -v xdg-open &> /dev/null; then
        xdg-open "https://github.com/zzlzzlzzl15/memora-knowledge-graph/actions"
    else
        echo "Please manually open: https://github.com/zzlzzlzzl15/memora-knowledge-graph/actions"
    fi
fi

echo ""
echo "🎉 Happy releasing!"
