#!/bin/bash

# Cleanup Script for GetMyEBook-Web
# Archives legacy SQLite database files and backup files

echo "========================================="
echo "GetMyEBook-Web Legacy Files Cleanup"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Create legacy directory
LEGACY_DIR="$PROJECT_ROOT/legacy"

echo -e "${BLUE}This script will archive the following legacy files:${NC}"
echo ""
echo "SQLite Database Files:"
echo "  - app.db (114 KB)"
echo "  - gdrive.db (24 KB)"
echo "  - metadata.db (118 KB)"
echo "  - ui-chacking/app.db"
echo "  - ui-chacking/metadaba.db"
echo ""
echo "Backup Files:"
echo "  - requirements.txt.old"
echo "  - cps/babel_bkp.py"
echo ""
echo -e "${YELLOW}These files will be moved to: ${LEGACY_DIR}${NC}"
echo ""

read -p "Do you want to proceed? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cleanup cancelled."
    exit 0
fi

# Create legacy directory
echo ""
echo "Creating legacy directory..."
mkdir -p "$LEGACY_DIR"
mkdir -p "$LEGACY_DIR/ui-chacking"
mkdir -p "$LEGACY_DIR/cps"

# Function to move file if it exists
move_file() {
    local source="$1"
    local dest="$2"
    
    if [ -f "$source" ]; then
        mv "$source" "$dest"
        echo -e "${GREEN}✓${NC} Moved: $source"
        return 0
    else
        echo -e "${YELLOW}⚠${NC} Not found: $source"
        return 1
    fi
}

# Move SQLite database files
echo ""
echo "Moving SQLite database files..."
move_file "$PROJECT_ROOT/app.db" "$LEGACY_DIR/app.db"
move_file "$PROJECT_ROOT/gdrive.db" "$LEGACY_DIR/gdrive.db"
move_file "$PROJECT_ROOT/metadata.db" "$LEGACY_DIR/metadata.db"
move_file "$PROJECT_ROOT/ui-chacking/app.db" "$LEGACY_DIR/ui-chacking/app.db"
move_file "$PROJECT_ROOT/ui-chacking/metadaba.db" "$LEGACY_DIR/ui-chacking/metadaba.db"

# Move backup files
echo ""
echo "Moving backup files..."
move_file "$PROJECT_ROOT/requirements.txt.old" "$LEGACY_DIR/requirements.txt.old"
move_file "$PROJECT_ROOT/cps/babel_bkp.py" "$LEGACY_DIR/cps/babel_bkp.py"

# Create README in legacy directory
echo ""
echo "Creating legacy directory README..."
cat > "$LEGACY_DIR/README.md" << 'EOF'
# Legacy Files Archive

This directory contains legacy files from the GetMyEBook-Web project that have been archived during the migration to PostgreSQL.

## Contents

### SQLite Database Files

These files were used in the old SQLite-based setup:

- `app.db` - Old application database
- `gdrive.db` - Old Google Drive database
- `metadata.db` - Old metadata database
- `ui-chacking/app.db` - Testing/backup database
- `ui-chacking/metadaba.db` - Testing/backup database

### Backup Files

- `requirements.txt.old` - Previous requirements file
- `cps/babel_bkp.py` - Backup babel configuration

## Migration Notes

The project now uses PostgreSQL for all database operations. These SQLite files are kept for reference and potential data migration needs.

## Restoration

If you need to restore any of these files:

```bash
# From the project root
cp legacy/filename.db ./
```

## Deletion

If you're certain you don't need these files:

```bash
# From the project root
rm -rf legacy/
```

**Warning**: This action is irreversible. Ensure you have backups if needed.

---

Archived on: $(date)
EOF

echo -e "${GREEN}✓${NC} Created: $LEGACY_DIR/README.md"

# Summary
echo ""
echo "========================================="
echo "Cleanup Complete!"
echo "========================================="
echo ""
echo -e "${GREEN}Legacy files have been archived to:${NC}"
echo "  $LEGACY_DIR"
echo ""
echo "You can:"
echo "  1. Keep the legacy directory for reference"
echo "  2. Delete it if you're certain you don't need the files:"
echo "     ${BLUE}rm -rf legacy/${NC}"
echo ""
echo -e "${YELLOW}Note: The legacy directory is gitignored and won't be committed.${NC}"
echo ""
