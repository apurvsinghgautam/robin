#!/usr/bin/env bash
#
# Robin Stack Management Script
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect docker compose command
if command -v docker-compose &> /dev/null; then
    COMPOSE="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    COMPOSE="docker compose"
else
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    exit 1
fi

print_header() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════╗"
    echo "║     Robin - Dark Web OSINT Agent      ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
}

print_usage() {
    echo "Usage: ./robin.sh <command>"
    echo ""
    echo "Commands:"
    echo "  up          Start all services"
    echo "  down        Stop all services"
    echo "  build       Build and start services"
    echo "  restart     Restart all services"
    echo "  logs        Tail logs from all services"
    echo "  logs:api    Tail backend API logs"
    echo "  logs:web    Tail frontend logs"
    echo "  logs:tor    Tail Tor proxy logs"
    echo "  status      Show service status"
    echo "  shell:api   Open shell in backend container"
    echo "  shell:db    Open psql shell in database"
    echo "  db:reset    Reset database (destructive)"
    echo "  clean       Remove all containers and volumes"
    echo "  setup-auth  Configure authentication"
    echo ""
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Error: Docker is not installed${NC}"
        exit 1
    fi
    if ! docker info &> /dev/null; then
        echo -e "${RED}Error: Docker daemon is not running${NC}"
        exit 1
    fi
}

check_auth() {
    if [[ -z "$ANTHROPIC_API_KEY" && -z "$CLAUDE_CODE_OAUTH_TOKEN" ]]; then
        if [[ ! -f "$HOME/.claude/settings.json" ]]; then
            echo -e "${YELLOW}Warning: No authentication configured${NC}"
            echo ""
            echo "Set one of the following:"
            echo "  export ANTHROPIC_API_KEY='your-api-key'"
            echo "  export CLAUDE_CODE_OAUTH_TOKEN='your-oauth-token'"
            echo ""
            echo "Or run: ./robin.sh setup-auth"
            echo ""
        fi
    fi
}

cmd_up() {
    check_auth
    echo -e "${GREEN}Starting Robin stack...${NC}"
    $COMPOSE up -d
    echo ""
    echo -e "${GREEN}Services started!${NC}"
    echo "  Frontend: http://localhost:3000"
    echo "  Backend:  http://localhost:8000"
    echo "  API Docs: http://localhost:8000/docs"
}

cmd_down() {
    echo -e "${YELLOW}Stopping Robin stack...${NC}"
    $COMPOSE down
    echo -e "${GREEN}Services stopped${NC}"
}

cmd_build() {
    check_auth
    echo -e "${GREEN}Building and starting Robin stack...${NC}"
    $COMPOSE up --build -d
    echo ""
    echo -e "${GREEN}Services started!${NC}"
    echo "  Frontend: http://localhost:3000"
    echo "  Backend:  http://localhost:8000"
    echo "  API Docs: http://localhost:8000/docs"
}

cmd_restart() {
    echo -e "${YELLOW}Restarting Robin stack...${NC}"
    $COMPOSE restart
    echo -e "${GREEN}Services restarted${NC}"
}

cmd_logs() {
    $COMPOSE logs -f
}

cmd_logs_api() {
    $COMPOSE logs -f backend
}

cmd_logs_web() {
    $COMPOSE logs -f frontend
}

cmd_logs_tor() {
    $COMPOSE logs -f tor
}

cmd_status() {
    echo -e "${BLUE}Service Status:${NC}"
    echo ""
    $COMPOSE ps
    echo ""

    # Check Tor connectivity
    if $COMPOSE ps tor | grep -q "Up"; then
        echo -e "Tor Proxy: ${GREEN}Running${NC}"
    else
        echo -e "Tor Proxy: ${RED}Not running${NC}"
    fi

    # Check auth
    echo ""
    echo -e "${BLUE}Authentication:${NC}"
    if [[ -n "$ANTHROPIC_API_KEY" ]]; then
        echo -e "  API Key: ${GREEN}Set${NC}"
    elif [[ -n "$CLAUDE_CODE_OAUTH_TOKEN" ]]; then
        echo -e "  OAuth Token: ${GREEN}Set${NC}"
    elif [[ -f "$HOME/.claude/settings.json" ]]; then
        echo -e "  Claude Config: ${GREEN}Mounted${NC}"
    else
        echo -e "  ${YELLOW}No authentication configured${NC}"
    fi
}

cmd_shell_api() {
    echo -e "${BLUE}Opening shell in backend container...${NC}"
    $COMPOSE exec backend /bin/bash || $COMPOSE exec backend /bin/sh
}

cmd_shell_db() {
    echo -e "${BLUE}Opening psql shell...${NC}"
    $COMPOSE exec db psql -U robin -d robin
}

cmd_db_reset() {
    echo -e "${RED}This will delete all investigation data!${NC}"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Resetting database...${NC}"
        $COMPOSE down -v
        $COMPOSE up -d db
        echo -e "${GREEN}Database reset complete${NC}"
    else
        echo "Cancelled"
    fi
}

cmd_clean() {
    echo -e "${RED}This will remove all containers, images, and volumes!${NC}"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Cleaning up...${NC}"
        $COMPOSE down -v --rmi local
        echo -e "${GREEN}Cleanup complete${NC}"
    else
        echo "Cancelled"
    fi
}

cmd_setup_auth() {
    echo -e "${BLUE}Authentication Setup${NC}"
    echo ""
    echo "Choose authentication method:"
    echo "  1) API Key (from console.anthropic.com)"
    echo "  2) OAuth Token (Claude Max subscription)"
    echo "  3) Cancel"
    echo ""
    read -p "Selection [1-3]: " choice

    case $choice in
        1)
            read -p "Enter your Anthropic API key: " api_key
            echo ""
            echo "Add to your shell profile (~/.bashrc, ~/.zshrc):"
            echo -e "${GREEN}export ANTHROPIC_API_KEY='$api_key'${NC}"
            echo ""
            echo "Or create a .env file:"
            echo "ANTHROPIC_API_KEY=$api_key" > .env
            echo -e "${GREEN}Created .env file${NC}"
            ;;
        2)
            echo ""
            echo "Run this command to generate a long-lived OAuth token:"
            echo -e "${GREEN}claude setup-token${NC}"
            echo ""
            echo "Then set the token:"
            echo -e "${GREEN}export CLAUDE_CODE_OAUTH_TOKEN='<your-token>'${NC}"
            echo ""
            read -p "Enter your OAuth token (or press Enter to skip): " oauth_token
            if [[ -n "$oauth_token" ]]; then
                echo "CLAUDE_CODE_OAUTH_TOKEN=$oauth_token" >> .env
                echo -e "${GREEN}Added to .env file${NC}"
            fi
            ;;
        *)
            echo "Cancelled"
            ;;
    esac
}

# Main
check_docker
print_header

case "${1:-}" in
    up)
        cmd_up
        ;;
    down)
        cmd_down
        ;;
    build)
        cmd_build
        ;;
    restart)
        cmd_restart
        ;;
    logs)
        cmd_logs
        ;;
    logs:api)
        cmd_logs_api
        ;;
    logs:web)
        cmd_logs_web
        ;;
    logs:tor)
        cmd_logs_tor
        ;;
    status)
        cmd_status
        ;;
    shell:api)
        cmd_shell_api
        ;;
    shell:db)
        cmd_shell_db
        ;;
    db:reset)
        cmd_db_reset
        ;;
    clean)
        cmd_clean
        ;;
    setup-auth)
        cmd_setup_auth
        ;;
    *)
        print_usage
        ;;
esac
