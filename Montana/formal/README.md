# Montana Formal Specifications

TLA+ formal specifications for Montana protocol verification.

## Files

| File | Description |
|------|-------------|
| `MontanaForkChoice.tla` | Fork choice rule and partition merge |
| `MontanaForkChoice.cfg` | TLC model checker configuration |

## Properties Verified

### Safety Properties

1. **SafetyOneCanonicalPerBoundary**: At most one canonical checkpoint per UTC boundary
2. **SafetyDeterministic**: Same inputs always produce same winner
3. **SafetyCanonicalExists**: Canonical checkpoint was actually created

### Invariants

1. **TypeInvariant**: All variables have correct types
2. **CommutativityInvariant**: `resolve(A, B) = resolve(B, A)`
3. **TransitivityInvariant**: If A beats B and B beats C, then A beats C
4. **Level4ReachableInvariant**: Hash tiebreaker only when all else equal

### Liveness Properties

1. **LivenessEventuallyCanonical**: Conflicting checkpoints eventually resolve

## Running TLC Model Checker

### Prerequisites

```bash
# Download TLA+ tools
wget https://github.com/tlaplus/tlaplus/releases/download/v1.8.0/tla2tools.jar
```

### Command Line

```bash
cd formal/
java -jar tla2tools.jar -config MontanaForkChoice.cfg MontanaForkChoice.tla
```

### TLA+ Toolbox IDE

1. Download from: https://lamport.azurewebsites.net/tla/toolbox.html
2. Open `MontanaForkChoice.tla`
3. Create model with constants from `.cfg` file
4. Run model checker

## Cascade Tiebreaker Specification

The fork choice rule is formally specified as:

```tla
ResolveCheckpointConflict(cp_a, cp_b) ==
    LET level1 == Level1Winner(cp_a, cp_b)  \* Participants count
        level2 == Level2Winner(cp_a, cp_b)  \* VDF iterations
        level3 == Level3Winner(cp_a, cp_b)  \* Aggregate score
        level4 == Level4Winner(cp_a, cp_b)  \* Hash (deterministic)
    IN
    IF level1 # "TIE" THEN level1
    ELSE IF level2 # "TIE" THEN level2
    ELSE IF level3 # "TIE" THEN level3
    ELSE level4
```

## Expected Results

With configuration in `.cfg`:

| Property | Expected | Status |
|----------|----------|--------|
| TypeInvariant | No violation | Verified |
| SafetyOneCanonicalPerBoundary | No violation | Verified |
| CommutativityInvariant | No violation | Verified |
| TransitivityInvariant | No violation | Verified |
| Level4ReachableInvariant | No violation | Verified |
| LivenessEventuallyCanonical | Holds | Verified |

## References

- Leslie Lamport, "Specifying Systems" (TLA+ book)
- MONTANA_TECHNICAL_SPECIFICATION.md §6.8, §6.9
- Yin et al., "HotStuff: BFT Consensus with Linearity and Responsiveness"
