# Montana App

**Post-quantum presence proof wallet for macOS**

Montana App tracks and proves your presence time, converting it into the universal currency **Ɉ** (Junona).

## Download

Download the latest release: [Montana v2.29.0](https://github.com/efir369999/-_Nothing_-/releases/latest)

## What is Montana?

Montana is a **presence-based currency system** where:
- **1 Ɉ = 1 second of verified human presence**
- No mining, no staking — just your time
- Post-quantum cryptography (ML-DSA-65 / Dilithium FIPS 204)
- Decentralized P2P network with instant finalization

## Features

### Presence Tracking
- **Weight-based presence model**: Base weight (always counting when app is running) + optional sensor anchors
- **Privacy-first**: Camera, microphone, location, Bluetooth used ONLY as anchors — no data collected or transmitted
- **Configurable sensors**: Enable/disable any sensor, app adapts weight automatically
- **VPN bonus**: +1 weight when connected to VPN (network privacy bonus)

### Wallet
- **Send/Receive Ɉ**: Transfer presence time to other users
- **QR codes**: Easy address sharing
- **Alias system**: Use `@username` instead of long addresses

### TimeChain Explorer
- **Live network view**: See all active addresses and their balances
- **Real-time updates**: Network state refreshes automatically
- **P2P sync**: < 1 second event propagation across global nodes

### Security
- **ML-DSA-65 signatures**: Post-quantum cryptographic security
- **Keychain storage**: Private keys secured in macOS Keychain
- **No cloud dependencies**: Fully local key management

## Technical Specs

- **Cryptography**: ML-DSA-65 (Dilithium) — NIST FIPS 204 post-quantum standard
- **Network**: 3-node P2P network (Amsterdam, Moscow, Almaty)
- **Consensus**: Instant finalization via deterministic EventLedger
- **Address format**: `mt` + SHA256(pubkey)[:20] = 42 characters
- **Privacy**: Zero data collection — sensors used only as presence anchors

## Installation

1. Download `Montana.app.zip`
2. Unzip and move `Montana.app` to Applications
3. Open Montana (menu bar app)
4. Grant permissions for presence sensors (optional)
5. Start earning Ɉ for your time

## System Requirements

- macOS 14.0 (Sonoma) or later
- Apple Silicon (M1/M2/M3) or Intel

## Genesis Price

**1 Ɉ = $0.1605 USD = 12.04₽ RUB**

- Price genesis: March 12, 2021 (BIPL — Bill Payment anchor)
- Montana genesis: January 9, 2026 (network launch)

## Protocol

Montana Protocol is based on the concept of **Ideal Money** — a universal settlement system where time is the fundamental unit of value.

- **Whitepaper**: [Montana Protocol Specification](../Русский/)
- **Network explorer**: Built into the app (TimeChain tab)
- **API docs**: See API server documentation

## Privacy & Permissions

Montana requests the following permissions (all optional):

- **Camera**: Presence anchor (video never recorded)
- **Microphone**: Ambient presence detection (audio never recorded)
- **Location**: Geographic presence proof (coordinates never transmitted)
- **Bluetooth**: Nearby device detection (MAC addresses never collected)

**You can disable all sensors and still earn Ɉ** — the app will use base weight (1 Ɉ/second).

## Network Architecture

Montana uses a **deterministic EventLedger** for consensus:

- All events have unique `event_id` (timestamp + node_id + sequence)
- Events are instantly pushed to all P2P nodes
- Balance calculation is deterministic by replaying all events
- No mining, no blocks, no PoW/PoS — just verifiable event history

## Development

Built with:
- SwiftUI (native macOS UI)
- ML-DSA-65 (dilithium_py)
- Python backend (Flask + EventLedger)
- P2P synchronization (< 1s propagation)

## Version History

### v2.29.0 (Feb 13, 2026)
- ✅ P2P synchronization fixes (port mismatch resolved)
- ✅ EventLedger balance consistency (wallets.json rebuilt)
- ✅ Duplicate event cleanup on Almaty node
- ✅ < 1 second event propagation across network

### v2.28.0
- TimeChain Explorer with live network view
- @alias support in Send tab
- Menu bar presence tick synchronization

### v2.27.0
- Full TimeChain Explorer (expandable details)
- P2P balance synchronization
- Version footer in all views

## License

Montana Protocol is an open, decentralized system. The reference implementation is provided as-is.

## Contact

- Website: [efir.org](https://efir.org) (coming soon)
- Protocol: Montana Protocol
- Network: 3 global nodes (Amsterdam, Moscow, Almaty)

---

**Time is the only real currency.** ⏱️ → Ɉ
