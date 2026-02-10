# Montana Presence

**Proof of Presence mining for macOS.** Earn Ɉ time coins while you're on camera.

Menu bar app that uses Apple Vision to detect your face. While you're present — on a video call, working, streaming — you earn Montana time coins (Ɉ).

## Install

### Option 1: One-line install
```bash
curl -fsSL https://raw.githubusercontent.com/efir369999/montana-presence/main/install.sh | bash
```

### Option 2: Download manually
Go to [Releases](https://github.com/efir369999/montana-presence/releases) and download `MontanaPresence.zip`.

Unzip it, then **right-click** the app → **Open** → confirm.

Or in Terminal:
```bash
xattr -cr MontanaPresence.app
open MontanaPresence.app
```

> **macOS Gatekeeper:** The app is not signed with an Apple Developer ID. This is normal for open-source software. `xattr -cr` removes the quarantine flag, or use right-click → Open.

### Option 3: Build from source
```bash
git clone https://github.com/efir369999/montana-presence.git
cd montana-presence
chmod +x build.sh
./build.sh
open MontanaPresence.app
```

## How it works

1. Click the **eye icon** in the menu bar
2. Open **Settings**, paste your Montana address (`mt...`)
3. Click **Start**
4. Camera turns on, Vision detects your face every 3 seconds
5. Face detected = you're **present** = earning Ɉ
6. Every 30 seconds, earned time is sent to Montana network
7. Works alongside FaceTime, Zoom, Google Meet

## Requirements

- macOS 14 (Sonoma) or later
- Apple Silicon (M1/M2/M3/M4)
- Camera access

## Architecture

```
Camera (352x288) → Vision (face detection, every 3 sec) → PresenceEngine (1 sec tick)
                                                                  ↓
                                                          API (4 nodes, failover)
                                                                  ↓
                                                          Montana Network → Ɉ
```

- **Face detection** runs locally via Apple Vision framework. No data leaves your Mac.
- **Presence** is sent as seconds to the Montana API. 1 second = 1 Ɉ (with halving).
- **Failover** across 4 Montana nodes. Works offline — pending seconds sync when back online.
- **Menu bar only** — no dock icon, no windows (unless you open Settings).

## Montana Protocol

Montana Protocol (Ɉ) — time-based digital currency with post-quantum cryptography (ML-DSA-65).

Time is the only resource distributed equally among all people. Montana digitizes presence and makes it currency.

- 1 second of presence = 1 Ɉ
- Halving every 4 years
- 21 million minutes total reserve
- Post-quantum from genesis

## License

MIT
