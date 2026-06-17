#!/bin/bash

# Version Bump Script for Memora Knowledge Graph
# Usage: ./bump_version.sh <version> [major|minor|patch]
# Example: ./bump_version.sh 2.1.0 minor

set -e

if [ -z "$1" ]; then
    echo "❌ Error: Please provide a version number"
    echo "Usage: $0 <version> [major|minor|patch]"
    echo "Example: $0 2.1.0 minor"
    exit 1
fi

NEW_VERSION="$1"
RELEASE_TYPE="${2:-manual}"

echo "🚀 Bumping version to v${NEW_VERSION} (${RELEASE_TYPE})"
echo ""

# Validate version format (semver)
if ! [[ $NEW_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "❌ Error: Invalid version format. Use semantic versioning (e.g., 2.1.0)"
    exit 1
fi

# Extract version components
IFS='.' read -r MAJOR MINOR PATCH <<< "$NEW_VERSION"

# Update package.json
echo "📝 Updating package.json..."
sed -i '' "s/\"version\": \"[0-9]\+\.[0-9]\+\.[0-9]\+\"/\"version\": \"${NEW_VERSION}\"/" package.json

# Update VERSION file
echo "📝 Updating VERSION file..."
echo "${NEW_VERSION}" > VERSION

# Update SKILL.md metadata
echo "📝 Updating SKILL.md..."
sed -i '' "s/version: [0-9]\+\.[0-9]\+\.[0-9]\+/version: ${NEW_VERSION}/" openclaw-skill/SKILL.md

# Update CSS version string in index.html (force cache refresh)
echo "📝 Updating CSS cache version in index.html..."
CSS_VERSION="kg-v${NEW_VERSION}-$(date +%Y%m%d)"
sed -i '' "s/style\.css?v=[^\"]*/style.css?v=${CSS_VERSION}/" static/index.html

# Add CHANGELOG entry if it doesn't exist
echo "📝 Checking CHANGELOG.md..."
if ! grep -q "\[${NEW_VERSION}\]" CHANGELOG.md; then
    echo "⚠️  Warning: No changelog entry found for v${NEW_VERSION}"
    echo "   Please add an entry to CHANGELOG.md before committing"
fi

echo ""
echo "✅ Version bumped to v${NEW_VERSION}!"
echo ""
echo "📋 Next steps:"
echo "   1. Review changes: git diff"
echo "   2. Commit changes: git commit -m \"chore: bump version to ${NEW_VERSION}\""
echo "   3. Push to main: git push origin main"
echo "   4. Create tag: git tag -a v${NEW_VERSION} -m \"Release v${NEW_VERSION}\""
echo "   5. Push tag: git push origin v${NEW_VERSION}"
echo ""
echo " GitHub Actions will automatically create the release!"
