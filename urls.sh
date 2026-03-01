#!/bin/bash
##############################################################################
# Quick reference for all LienHunter v2 URLs on DGX
##############################################################################

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}LienHunter v2 — System URLs (DGX)${NC}"
echo -e "${BLUE}========================================${NC}
"

echo -e "${YELLOW}🌍 Web Frontend:${NC}"
echo -e "  Dashboard:       ${BLUE}http://192.168.100.133:8083${NC}"
echo ""

echo -e "${YELLOW}⚙️  Backend & Documentation:${NC}"
echo -e "  API Base:        ${BLUE}http://192.168.100.133:8001${NC}"
echo -e "  API Interactive: ${BLUE}http://192.168.100.133:8001/docs${NC}"
echo -e "  Investor Playbook:${BLUE}http://192.168.100.133:8001/playbook${NC}"
echo -e "  Getting Started: ${BLUE}http://192.168.100.133:8001/getting-started${NC}"
echo -e "  Quick Start:     ${BLUE}http://192.168.100.133:8001/instructions${NC}"
echo ""

echo -e "${YELLOW}🗄️  Database Access:${NC}"
echo -e "  External Host:   ${BLUE}192.168.100.133${NC}"
echo -e "  External Port:   ${BLUE}3307${NC}"
echo -e "  Database:        ${BLUE}lienhunter${NC}"
echo -e "  Username:        ${BLUE}lienuser${NC}"
echo ""

echo -e "${BLUE}========================================${NC}"
