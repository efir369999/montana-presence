#!/bin/bash
# Proof of Time Testnet Launcher
# Version: 2.0.0 Pantheon

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_banner() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║                                                          ║"
    echo "║     ██████╗  ██████╗ ████████╗                          ║"
    echo "║     ██╔══██╗██╔═══██╗╚══██╔══╝                          ║"
    echo "║     ██████╔╝██║   ██║   ██║                             ║"
    echo "║     ██╔═══╝ ██║   ██║   ██║                             ║"
    echo "║     ██║     ╚██████╔╝   ██║                             ║"
    echo "║     ╚═╝      ╚═════╝    ╚═╝                             ║"
    echo "║                                                          ║"
    echo "║         Proof of Time Testnet v2.0.0 Pantheon           ║"
    echo "║                                                          ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

check_dependencies() {
    echo "Checking dependencies..."

    if ! command -v docker &> /dev/null; then
        print_error "Docker not found. Please install Docker."
        exit 1
    fi
    print_status "Docker found"

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose not found. Please install Docker Compose."
        exit 1
    fi
    print_status "Docker Compose found"

    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 not found. Please install Python 3.11+."
        exit 1
    fi
    print_status "Python 3 found"

    echo ""
}

generate_genesis() {
    echo "Generating genesis block..."
    cd "$PROJECT_DIR"
    python3 testnet/genesis.py
    print_status "Genesis block generated"
    echo ""
}

start_testnet() {
    echo "Starting testnet..."
    cd "$SCRIPT_DIR"

    # Use docker compose (v2) or docker-compose (v1)
    if docker compose version &> /dev/null; then
        docker compose up -d
    else
        docker-compose up -d
    fi

    print_status "Testnet started"
    echo ""

    echo "Waiting for nodes to sync..."
    sleep 10

    echo ""
    echo -e "${GREEN}Testnet is running!${NC}"
    echo ""
    echo "Nodes:"
    echo "  - Seed 1: http://localhost:9334 (P2P: 9333)"
    echo "  - Seed 2: http://localhost:9336 (P2P: 9335)"
    echo "  - Seed 3: http://localhost:9338 (P2P: 9337)"
    echo ""
    echo "Services:"
    echo "  - Faucet:   http://localhost:9340"
    echo "  - Explorer: http://localhost:9341"
    echo ""
}

stop_testnet() {
    echo "Stopping testnet..."
    cd "$SCRIPT_DIR"

    if docker compose version &> /dev/null; then
        docker compose down
    else
        docker-compose down
    fi

    print_status "Testnet stopped"
}

reset_testnet() {
    echo "Resetting testnet (WARNING: This will delete all data)..."
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        stop_testnet

        cd "$SCRIPT_DIR"
        if docker compose version &> /dev/null; then
            docker compose down -v
        else
            docker-compose down -v
        fi

        print_status "Testnet reset complete"
    else
        print_warning "Reset cancelled"
    fi
}

show_logs() {
    cd "$SCRIPT_DIR"
    if docker compose version &> /dev/null; then
        docker compose logs -f "${1:-}"
    else
        docker-compose logs -f "${1:-}"
    fi
}

show_status() {
    cd "$SCRIPT_DIR"
    echo "Testnet Status:"
    echo ""

    if docker compose version &> /dev/null; then
        docker compose ps
    else
        docker-compose ps
    fi

    echo ""
    echo "Checking node health..."

    for port in 9334 9336 9338; do
        if curl -s "http://localhost:$port/health" > /dev/null 2>&1; then
            print_status "Node on port $port is healthy"
        else
            print_warning "Node on port $port is not responding"
        fi
    done
}

run_local() {
    echo "Running single node locally (no Docker)..."
    cd "$PROJECT_DIR"

    # Generate genesis if not exists
    if [ ! -f "$SCRIPT_DIR/genesis.json" ]; then
        generate_genesis
    fi

    # Run node
    python3 node.py --run --config testnet/config.json
}

# Main
print_banner

case "${1:-help}" in
    start)
        check_dependencies
        generate_genesis
        start_testnet
        ;;
    stop)
        stop_testnet
        ;;
    restart)
        stop_testnet
        sleep 2
        start_testnet
        ;;
    reset)
        reset_testnet
        ;;
    logs)
        show_logs "$2"
        ;;
    status)
        show_status
        ;;
    local)
        run_local
        ;;
    genesis)
        generate_genesis
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|reset|logs|status|local|genesis}"
        echo ""
        echo "Commands:"
        echo "  start    - Start the testnet (3 nodes + faucet + explorer)"
        echo "  stop     - Stop the testnet"
        echo "  restart  - Restart the testnet"
        echo "  reset    - Reset testnet (delete all data)"
        echo "  logs     - Show logs (optional: node name)"
        echo "  status   - Show testnet status"
        echo "  local    - Run single node locally (no Docker)"
        echo "  genesis  - Generate genesis block only"
        echo ""
        ;;
esac
