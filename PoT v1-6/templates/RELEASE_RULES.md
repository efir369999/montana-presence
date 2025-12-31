# Release Rules - Proof of Time Protocol

## Version Numbering

```
MAJOR.MINOR.PATCH
  │     │     └── Bug fixes, security patches
  │     └──────── New features, non-breaking changes
  └────────────── Breaking changes, major rewrites
```

**Current Version: v4.3.0**

---

## Pre-Release Checklist

### 1. Code Analysis
- [ ] Compare all commits since previous version
- [ ] Identify new features, fixes, and breaking changes
- [ ] Verify all tests pass: `python -m pytest tests/ -v`
- [ ] Run security audit: `python tests/test_security_proofs.py`
- [ ] Check for dead code and unused imports

### 2. Module Status (11 Gods)

| Module | Status | Description |
|--------|--------|-------------|
| ADAM | Production | God of Time (7 levels, Bitcoin anchor) |
| PAUL | Production | Network (P2P, Noise Protocol) |
| HADES | Production | Storage (SQLite, DAG) |
| ATHENA | Production | Consensus (DAG ordering, finality) |
| PROMETHEUS | Production | Crypto (VDF, VRF, ECVRF) |
| PLUTUS | Production | Wallet (Argon2id, AES-256-GCM) |
| NYX | Production | Privacy (T0/T1 only) |
| THEMIS | Production | Validation (blocks, transactions) |
| IRIS | Production | RPC Server (JSON-RPC 2.0) |
| APOSTLES | Production | Trust (12 bootstrap nodes) |
| HAL | Production | Human Analyse Language (reputation, Sybil, slashing) |

### 3. Documentation
- [ ] Update version in `README.md` (badge, installation, features)
- [ ] Update version in `ROADMAP.md` (current status, next milestones)
- [ ] Create new `Montana_vX.X.md` whitepaper (see Whitepaper Rules below)
- [ ] Regenerate `Montana_vX.X.pdf`
- [ ] Update `PANTHEON.md` if module structure changed

---

## Whitepaper Rules (Montana Style)

### Core Principle
**Каждый релиз = новый whitepaper с нуля.**

Montana - это не changelog. Это полная архитектурная спецификация текущей версии.
Любой AI агент должен по одному документу понять всю систему.

### Requirements

1. **Версия = Релиз**
   - `Montana_v4.3.md` → релиз v4.3.0
   - Никаких "updated from v4.2" - документ самодостаточен

2. **Написан как в первый раз**
   - Без истории изменений внутри документа
   - Без "previously we had X, now Y"
   - Без deprecated warnings
   - Читатель не знает предыдущих версий

3. **Полная спецификация**
   - Все 11 богов Пантеона с описанием
   - Все криптографические примитивы
   - Все структуры данных (блоки, транзакции)
   - Все консенсусные параметры
   - Network protocol details
   - Privacy model (текущий, без removed features)

4. **AI-Agent Readable**
   - Структура: Overview → Architecture → Modules → Crypto → Consensus → Network
   - Чёткие code examples для каждого модуля
   - ASCII diagrams для data flow
   - Explicit imports и function signatures

5. **Стиль Montana**
   - Короткие предложения
   - Технические факты без воды
   - Прямые утверждения ("uses", "implements", не "may use")
   - Формат: `Module: What it does. How it works. Code example.`

### Template Structure

```markdown
# Proof of Time Protocol - Montana vX.X

## Overview
[2-3 paragraphs: What is PoT, core innovation, security model]

## Architecture
[ASCII diagram of system components]
[11 Pantheon gods table with responsibilities]

## Temporal Consensus (ADAM)
[7 levels, VDF specs, Bitcoin anchoring]

## Network Layer (PAUL)
[P2P protocol, Noise XX, message types]

## Storage (HADES)
[SQLite schema, DAG structure, indexes]

## Consensus Engine (ATHENA)
[DAG ordering, finality, fork resolution]

## Cryptography (PROMETHEUS)
[VDF, VRF, ECVRF, hash functions]

## Wallet (PLUTUS)
[Key derivation, encryption, transaction signing]

## Privacy (NYX)
[Current privacy tiers, stealth addresses]

## Validation (THEMIS)
[Block validation, transaction validation]

## RPC Interface (IRIS)
[JSON-RPC methods, WebSocket]

## Trust Network (APOSTLES)
[12 bootstrap nodes, trust scoring]

## HAL: Human Analyse Language
[Reputation, Sybil detection, slashing]

## Appendix
[Constants, parameters, test vectors]
```

### Anti-Patterns (ЗАПРЕЩЕНО)

- ❌ "In v4.2 we had X, now in v4.3..."
- ❌ "Deprecated: use Y instead"
- ❌ "Legacy support for..."
- ❌ "Migration from previous version"
- ❌ Ссылки на старые версии документа
- ❌ Changelog внутри whitepaper

### Correct Examples

```markdown
# CORRECT
NYX implements T0 (Public) and T1 (Stealth Address) privacy tiers.
Stealth addresses use ECDH with Curve25519.

# WRONG
NYX previously supported T2/T3 tiers but they were removed in v4.2.
Now only T0 and T1 are available.
```

---

## Release Process

### Step 1: Version Bump

```bash
# Create new whitepaper version
cp Montana_v4.2.md Montana_v4.3.md
# Update version inside the file
```

### Step 1.5: PDF Generation

**CRITICAL: Символ Ɉ (U+0248)**

Символ валюты Ɉ (Latin Capital Letter J with Stroke) требует шрифт с поддержкой Latin Extended-B.

**Поддерживаемые шрифты (macOS):**
- Helvetica / Helvetica Neue ✅
- Geneva ✅
- Times New Roman ✅
- Baskerville ✅
- Arial ✅

**НЕ поддерживают Ɉ:**
- DejaVu Sans ❌
- Noto Sans (большинство вариантов) ❌
- Многие системные шрифты Linux ❌

**Генерация PDF:**
```bash
# Используй templates/pdf_style.css который указывает правильные шрифты
pandoc Montana_vX.X.md -o temp.html --metadata title="Montana vX.X" --standalone
weasyprint temp.html Montana_vX.X.pdf --stylesheet=templates/pdf_style.css
rm temp.html
```

**Проверка поддержки шрифта:**
```bash
# Найти шрифты поддерживающие U+0248
fc-list :charset=0248

# Должен показать Helvetica, Geneva, etc.
```

**Если Ɉ отображается криво:**
1. Проверь что `templates/pdf_style.css` использует Helvetica первым
2. Убедись что шрифт установлен в системе
3. На Linux установи: `apt install fonts-dejavu-core ttf-mscorefonts-installer`

### Step 2: Commit Changes

```bash
git add -A
git commit -m "docs: Update whitepaper and README to v4.3"
git push origin main
```

### Step 3: Create Git Tag

```bash
git tag -a v4.3.0 -m "v4.3.0: [RELEASE_TITLE]"
git push origin v4.3.0
```

### Step 4: GitHub Release

```bash
gh release create v4.3.0 \
  --title "v4.3.0: [RELEASE_TITLE]" \
  --notes-file RELEASE_NOTES.md \
  Montana_v4.3.pdf
```

---

## Release Notes Template

```markdown
# v4.3.0: [RELEASE_TITLE]

## Summary
[1-2 sentence overview of this release]

## Breaking Changes
- [List any breaking changes]

## New Features
- [List new features]

## Bug Fixes
- [List bug fixes]

## Security
- [List security improvements]

## Module Changes
- [List module additions/removals/renames]

## Migration Guide
[If breaking changes exist, explain how to migrate]

## Full Changelog
[Link to compare: vX.X.X...vY.Y.Y]
```

---

## v4.3.0 Changelog (from v4.2.0)

### New Modules
- **ADAM** (`pantheon/adam/`) - God of Time
  - Merged from AdamSync + Chronos
  - 7 temporal levels with Bitcoin anchoring
  - VDF fallback to VRF

- **HAL Extensions** (`pantheon/hal/`)
  - `behavioral.py` - Sybil detection, cluster analysis
  - `slashing.py` - SlashingManager moved from ATHENA
  - `reputation.py` - Merged from Adonis

### Renamed Modules
- **HERMES → PAUL** - Peer Authenticated Unified Link
  - Same functionality, new name

### Deleted Modules
- `pantheon/chronos/` - Merged into ADAM
- `pantheon/adonis/` - Merged into HAL
- `pantheon/ananke/` - Empty stub removed
- `pantheon/mnemosyne/` - Empty stub removed

### Deleted Files
- `pantheon/athena/bitcoin_oracle.py` - Duplicate of ADAM
- `pantheon/athena/vdf_fallback.py` - Duplicate of ADAM
- `pantheon/nyx/ristretto.py` - Experimental, removed

### Security Fixes
- Replace `random.randint` with `secrets.randbits` in network.py
- Replace `random.sample` with `secrets.SystemRandom` in pq_crypto.py
- Fix VDF fallback STARK verify (was returning True when unavailable)

### Production Ready
All 11 modules are now production-ready:
- Explicit `__all__` exports (no wildcards)
- Dead imports removed
- ASCII documentation headers
- Type hints throughout

### Stats
```
55 files changed
5,152 insertions(+)
8,840 deletions(-)
```

---

## Audit Checklist

### Security Audit
- [ ] SQL injection: Parameterized queries only
- [ ] Command injection: No user input in shell commands
- [ ] Timing attacks: `hmac.compare_digest` for secrets
- [ ] Random numbers: `secrets` module for crypto
- [ ] Key storage: Argon2id for KDF
- [ ] Network: Noise Protocol XX encryption

### Code Quality
- [ ] No `import *` (wildcard imports)
- [ ] No dead code or unused imports
- [ ] All functions have docstrings
- [ ] Type hints on public APIs
- [ ] Tests for new features

### Test Coverage
- [ ] `test_integration.py` - 48 tests
- [ ] `test_dag.py` - 48 tests
- [ ] `test_fuzz.py` - 27 tests
- [ ] `test_stress.py` - Stress/load tests
- [ ] `test_security_proofs.py` - Security proofs

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| v4.3.0 | 2024-12-30 | Module consolidation (ADAM, HAL merge) |
| v4.2.1 | 2024-12-XX | Bitcoin-anchored TIME dimension |
| v4.2.0 | 2024-12-XX | HAL: Human Analyse Language |
| v4.0.0 | 2024-12-XX | Montana - Bitcoin Time Oracle |
| v3.1.0 | 2024-12-XX | Security hardening |
