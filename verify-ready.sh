#!/bin/bash
# Verification script to check if Arrmate is ready for publishing

echo "🔍 Arrmate Publishing Readiness Check"
echo "======================================"
echo ""

ERRORS=0
WARNINGS=0

# Check 1: Directory name
echo "📁 Checking directory name..."
CURRENT_DIR=$(basename "$PWD")
if [ "$CURRENT_DIR" = "arrmate" ]; then
    echo "   ✅ Directory is named 'arrmate'"
else
    echo "   ❌ Directory should be named 'arrmate' (currently: $CURRENT_DIR)"
    echo "      Run: cd .. && mv $CURRENT_DIR arrmate && cd arrmate"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check 2: mediatools references
echo "🔎 Checking for remaining 'mediatools' references..."
MEDIATOOLS_COUNT=$(grep -r "mediatools" . --exclude-dir=.git --exclude-dir=venv --exclude-dir=__pycache__ --exclude-dir=.claude --exclude="*.sh" 2>/dev/null | wc -l)
if [ "$MEDIATOOLS_COUNT" -eq 0 ]; then
    echo "   ✅ No 'mediatools' references found"
else
    echo "   ⚠️  Found $MEDIATOOLS_COUNT references to 'mediatools'"
    echo "      Run: grep -r 'mediatools' . --exclude-dir=.git --exclude-dir=venv"
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

# Check 3: YOURUSERNAME placeholders
echo "👤 Checking for YOURUSERNAME placeholders..."
YOURUSERNAME_COUNT=$(grep -r "YOURUSERNAME" . --exclude-dir=.git --exclude-dir=venv --exclude-dir=.claude --exclude="*.sh" --exclude="*.md" 2>/dev/null | wc -l)
if [ "$YOURUSERNAME_COUNT" -gt 0 ]; then
    echo "   ❌ Found $YOURUSERNAME_COUNT instances of 'YOURUSERNAME' that need to be replaced"
    echo "      Files to update:"
    grep -r "YOURUSERNAME" . --exclude-dir=.git --exclude-dir=venv --exclude-dir=.claude --exclude="*.sh" --exclude="*.md" -l 2>/dev/null | sed 's/^/      - /'
    ERRORS=$((ERRORS + 1))
else
    echo "   ✅ All YOURUSERNAME placeholders replaced"
fi
echo ""

# Check 4: Required files exist
echo "📄 Checking required files..."
REQUIRED_FILES=(
    "README.md"
    "LICENSE"
    "pyproject.toml"
    "requirements.txt"
    ".env.example"
    ".gitignore"
    "CONTRIBUTING.md"
    ".github/FUNDING.yml"
    "docs/index.html"
    "docker/Dockerfile"
    "docker/docker-compose.yml"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✅ $file"
    else
        echo "   ❌ Missing: $file"
        ERRORS=$((ERRORS + 1))
    fi
done
echo ""

# Check 5: Python package structure
echo "🐍 Checking Python package..."
if [ -d "src/arrmate" ]; then
    echo "   ✅ Package directory exists: src/arrmate"
else
    echo "   ❌ Package directory missing: src/arrmate"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check 6: Git repository
echo "📦 Checking git repository..."
if [ -d ".git" ]; then
    echo "   ✅ Git repository initialized"

    # Check if there's a remote
    if git remote -v &>/dev/null && [ "$(git remote -v | wc -l)" -gt 0 ]; then
        echo "   ✅ Git remote configured"
        git remote -v | sed 's/^/      /'
    else
        echo "   ⚠️  No git remote configured yet"
        echo "      Will need to add remote before pushing"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo "   ⚠️  Git not initialized yet"
    echo "      Run: git init"
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

# Check 7: Documentation
echo "📚 Checking documentation..."
DOC_FILES=(
    "QUICKSTART.md"
    "PUBLISHING_GUIDE.md"
    "LAUNCH_CHECKLIST.md"
    "DOCKER_HUB_GUIDE.md"
)

for file in "${DOC_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✅ $file"
    else
        echo "   ⚠️  Missing: $file (optional but recommended)"
        WARNINGS=$((WARNINGS + 1))
    fi
done
echo ""

# Summary
echo "======================================"
echo "📊 Summary"
echo "======================================"
echo ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "✅ All checks passed! Arrmate is ready for publishing!"
    echo ""
    echo "Next steps:"
    echo "1. Follow LAUNCH_CHECKLIST.md"
    echo "2. Create GitHub repository"
    echo "3. Push code"
    echo "4. Create v0.1.0 release"
    echo "5. Share with testers!"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo "⚠️  Ready with warnings ($WARNINGS warnings)"
    echo ""
    echo "You can proceed, but consider fixing the warnings."
    echo "Follow LAUNCH_CHECKLIST.md for next steps."
    exit 0
else
    echo "❌ Not ready ($ERRORS errors, $WARNINGS warnings)"
    echo ""
    echo "Please fix the errors above before publishing."
    echo "See REBRANDING_COMPLETE.md for help."
    exit 1
fi
