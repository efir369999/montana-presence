# Ɉ Montana

**Time-Proven Human Temporal Currency**

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()
[![PoT v6](https://img.shields.io/badge/PoT-v6.1.0-purple.svg)]()

---

## Overview

Ɉ Montana ($MONT) is a decentralized time-based cryptocurrency built on the Proof of Time (PoT v6) protocol. Unlike Proof of Work or Proof of Stake, Proof of Time uses temporal presence as the basis for consensus—a resource that cannot be accumulated, purchased, or transferred.

**Time cannot be bought—only spent. Humanity cannot be faked—only proven.**

## Features

- **Three-Layer Participation**: Server (50%), Telegram Bot (30%), User Game (15%)
- **Chico Time Game**: Gamified time verification via Telegram
- **Five Fingers of Adonis**: Multi-dimensional reputation system
- **Twelve Apostles**: Trust bond network with collective accountability
- **HAL Humanity System**: Sybil resistance through humanity proof
- **Post-Quantum Security**: SPHINCS+, SHA3-256, ML-KEM-768

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/proofoftime/montana.git
cd montana

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Run Telegram Bot

```bash
# Set your Telegram bot token
export TELEGRAM_BOT_TOKEN="your_token_here"

# Run the bot
python -m montana.bot.main
```

### Run Full Node

```bash
# Start the Montana node
python -m montana.node.node
```

## Tokenomics

| Parameter | Value |
|-----------|-------|
| Name | Montana |
| Symbol | Ɉ |
| Ticker | $MONT |
| Total Supply | 1,260,000,000 Ɉ |
| Unit | 1 Ɉ = 1 second |
| Block Time | 10 minutes |
| Initial Reward | 50 minutes/block |
| Halving Interval | 210,000 blocks (~4 years) |

## Three-Layer Participation

```
┌─────────────────────────────────────────────────────────────┐
│  MONTANA PARTICIPATION LAYERS                               │
├─────────────────────────────────────────────────────────────┤
│  Layer 0: SERVER    │ Weight 0.50 │ Full node operators    │
│  Layer 1: BOT       │ Weight 0.30 │ Telegram users         │
│  Layer 2: USER      │ Weight 0.15 │ Chico Time game        │
└─────────────────────────────────────────────────────────────┘
```

## Chico Time Game

*"Сколько на твоих часах, Чико?"*

Play the time verification game in Telegram:

1. Type `/time` in the bot
2. Choose from 5 time options
3. Correct answer (±2 min): +10 points
4. Wrong answer: -2 points

## Documentation

- [Whitepaper](WHITEPAPER.md) - Full project documentation
- [Technical Specification](TECHNICAL_SPEC.md) - Implementation details

## Architecture

```
Montana (Application)
    │
    ├── Telegram Bot
    ├── Node
    ├── API (JSON-RPC)
    └── Storage (SQLite)
         │
         ▼
PoT v6 (Protocol Library)
    │
    ├── Layer 0: Atomic Time (34 NTP sources)
    ├── Layer 1: VDF + STARK
    ├── Layer 2: Bitcoin Anchor
    ├── Crypto: SPHINCS+, SHA3, SHAKE256
    └── Consensus: W-MSR
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Register account |
| `/time` | Play Chico Time |
| `/balance` | Check balance |
| `/send @user 100` | Send Ɉ |
| `/apostles` | Manage trust bonds |
| `/stats` | View reputation |

## Development

### Project Structure

```
Montana/
├── WHITEPAPER.md
├── TECHNICAL_SPEC.md
├── README.md
├── requirements.txt
│
├── montana/
│   ├── bot/          # Telegram bot
│   ├── layers/       # Participation layers
│   ├── reputation/   # Five Fingers + Apostles
│   ├── node/         # Full node
│   ├── api/          # JSON-RPC
│   └── storage/      # Database
│
└── tests/
```

### Running Tests

```bash
pytest tests/
```

## License

MIT License

## Author

Alejandro Montana
alejandromontana@tutamail.com

---

*"Running bitcoin" — Hal Finney, January 2009*

**Ɉ**
