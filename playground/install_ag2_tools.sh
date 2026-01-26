#!/bin/bash

# AG2 Free Tools Installation Script
# This script installs all dependencies needed for AG2 free tools integration

set -e

echo "=================================================="
echo "AG2 Free Tools Installation"
echo "=================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

if ! python3 -c 'import sys; exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
    echo -e "${RED}Error: Python 3.12 or higher is required${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python version OK${NC}"
echo ""

# Install AG2 with interoperability support
echo "Installing AG2 with interoperability support..."
pip install -U "ag2[openai,interop-langchain,interop-crewai,duckduckgo]" || {
    echo -e "${RED}Failed to install AG2 with interop${NC}"
    exit 1
}
echo -e "${GREEN}✓ AG2 installed${NC}"
echo ""

# Install LangChain Community
echo "Installing LangChain Community..."
pip install langchain-community || {
    echo -e "${RED}Failed to install langchain-community${NC}"
    exit 1
}
echo -e "${GREEN}✓ LangChain Community installed${NC}"
echo ""

# Install CrewAI with tools
echo "Installing CrewAI with tools..."
pip install 'crewai[tools]' || {
    echo -e "${RED}Failed to install CrewAI tools${NC}"
    exit 1
}
echo -e "${GREEN}✓ CrewAI tools installed${NC}"
echo ""

# Install free tool dependencies
echo "Installing free tool dependencies..."

echo "  - DuckDuckGo Search..."
pip install duckduckgo-search || echo -e "${YELLOW}⚠ DuckDuckGo search optional dependency failed${NC}"

echo "  - Wikipedia..."
pip install wikipedia || echo -e "${YELLOW}⚠ Wikipedia optional dependency failed${NC}"

echo "  - ArXiv..."
pip install arxiv || echo -e "${YELLOW}⚠ ArXiv optional dependency failed${NC}"

echo -e "${GREEN}✓ Tool dependencies installed${NC}"
echo ""

# Verify installation
echo "Verifying installation..."
python3 << 'EOF'
try:
    from autogen.interop import Interoperability
    print("✓ AG2 Interoperability available")
except ImportError as e:
    print(f"✗ AG2 Interoperability not available: {e}")
    exit(1)

try:
    from langchain_community.tools import DuckDuckGoSearchRun
    print("✓ LangChain tools available")
except ImportError as e:
    print(f"⚠ LangChain tools issue: {e}")

try:
    from crewai_tools import ScrapeWebsiteTool
    print("✓ CrewAI tools available")
except ImportError as e:
    print(f"⚠ CrewAI tools issue: {e}")

print("\n✓ Installation verification complete!")
EOF

if [ $? -eq 0 ]; then
    echo ""
    echo "=================================================="
    echo -e "${GREEN}Installation Complete!${NC}"
    echo "=================================================="
    echo ""
    echo "Next steps:"
    echo "1. Set your OpenAI API key:"
    echo "   export OPENAI_API_KEY='your-key-here'"
    echo ""
    echo "2. Try the examples:"
    echo "   python examples/ag2_free_tools_example.py"
    echo ""
    echo "3. Read the documentation:"
    echo "   docs/AG2_FREE_TOOLS_GUIDE.md"
    echo ""
else
    echo ""
    echo "=================================================="
    echo -e "${RED}Installation had some issues${NC}"
    echo "=================================================="
    echo "Please check the error messages above"
    exit 1
fi
