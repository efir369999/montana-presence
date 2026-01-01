# Layer -1 — Physical Constraints

-----

## L-1.0 Scope and Epistemological Status

Layer -1 enumerates physical constraints that bound all possible protocols.

This layer contains no protocol logic, no cryptographic assumptions, no design decisions.

**Epistemological claim:** The statements below represent our best empirically-verified models of physical reality. They have been tested to precisions specified in each section, with no observed violations. We do not claim metaphysical certainty—we claim that any system assuming these constraints will fail only if physics itself requires fundamental revision at scales and energies relevant to terrestrial computation.

**Foundational axiom:** We assume any adversary operates within known physics. This is the minimal assumption required for "security" to be meaningful. An adversary unconstrained by physics could violate mathematical axioms themselves.

-----

## L-1.1 Thermodynamic Arrow

**Constraint:** In any macroscopic isolated system, total entropy does not decrease over protocol-relevant timescales (< 10¹⁰ years), except with probability exponentially suppressed by particle count.

**Formal basis:** Second Law of Thermodynamics (statistical mechanics formulation).

**Quantitative statement:** For a system of N particles undergoing a thermodynamic process, the probability of observing a net entropy decrease ΔS < 0 is bounded by:

$$P(\Delta S < 0) \sim \exp\left(-\frac{|\Delta S|}{k_B}\right)$$

For macroscopic systems (N ~ 10²³), even a microscopic entropy decrease of |ΔS| ~ 10⁻²⁰ J/K yields:

$$P \sim \exp\left(-\frac{10^{-20}}{1.381 \times 10^{-23}}\right) = \exp(-724) \approx 10^{-315}$$

**Empirical status:** No macroscopic violation observed in over 150 years of thermodynamic measurements. The fluctuation theorem (Evans et al., 1993; Wang et al., 2002) confirms the statistical formulation at microscopic scales, with violations observable only for nanoscale systems over sub-second timescales.

**Important clarification:** The Second Law is statistical, not absolute. The fluctuation theorem quantifies the probability of transient entropy decreases in small systems. For a system experiencing entropy change ΔS over time τ:

$$\frac{P(\Delta S)}{P(-\Delta S)} = \exp\left(\frac{\Delta S}{k_B}\right)$$

This means microscopic violations occur constantly but cancel statistically. For macroscopic systems, the probability of observable net violations is negligible over any protocol-relevant timescale.

**Timescale clarification:** The Poincaré recurrence theorem guarantees eventual return to low-entropy states in finite bounded systems, but recurrence times for macroscopic systems exceed 10^(10²³) years—far beyond any protocol-relevant consideration.

**Implication for protocols:** Macroscopic state transitions have irreversible causal ordering. If state B is derived from state A through an entropy-increasing process, B cannot precede A. This provides a physical arrow of time independent of any protocol definition.

-----

## L-1.2 Reproducibility of Atomic Time Standards

**Constraint:** Isolated atoms of a given isotope, in identical quantum states, exhibit identical transition frequencies in their local inertial frames.

**Formal basis:** Quantum mechanics—atomic energy levels are determined by fundamental constants (electron mass, elementary charge, Planck constant, speed of light). Any variation would require these constants to vary.

**Empirical status:**

| Clock type | Isotope | Reproducibility | Source |
|---|---|---|---|
| Cesium fountain | ¹³³Cs | Δf/f < 2 × 10⁻¹⁶ | BIPM inter-comparisons (NIST, PTB, NPL, SYRTE) |
| Optical lattice | ⁸⁷Sr | Δf/f < 2 × 10⁻¹⁸ | Bothwell et al., 2022 (JILA) |
| Optical lattice | ¹⁷¹Yb | Δf/f < 1.4 × 10⁻¹⁸ | McGrew et al., 2018 (NIST) |
| Optical ion | ²⁷Al⁺ | Δf/f < 9.4 × 10⁻¹⁹ | Brewer et al., 2019 (NIST) |

**Note on SI second:** The SI definition (9,192,631,770 Hz for the ¹³³Cs hyperfine transition at 0 K, at rest, at sea level) is a metrological convention, not a physical law. The physical law is that this frequency is reproducible across independent realizations to the precisions stated above.

**Limits on fundamental constant variation:** Astronomical observations and laboratory measurements constrain time variation of the fine structure constant α to |α̇/α| < 10⁻¹⁷ per year (Rosenband et al., 2008), supporting the stability assumption.

**Implication for protocols:** Locally-realizable, universally-reproducible time measurement exists. Independent parties can establish synchronized clocks without shared trust infrastructure, limited only by signal propagation delays (L-1.4) and relativistic corrections (L-1.5).

-----

## L-1.3 Landauer Limit

**Constraint:** Irreversibly erasing one bit of information in a system at temperature T dissipates at least kT ln(2) of energy into the environment.

**Formal basis:** Statistical mechanics applied to information theory. Landauer (1961) showed that logical irreversibility implies thermodynamic irreversibility. Bennett (1982) clarified that the limit applies specifically to erasure, not computation generally.

**Derivation:** Erasing a bit reduces the system's Shannon entropy by 1 bit = ln(2) nats. By the second law, this entropy must be expelled to the environment as heat Q ≥ kT ln(2).

**Value at T = 300 K:**

$$E_{\min} = k_B T \ln(2) = (1.380649 \times 10^{-23}\ \text{J/K}) \times (300\ \text{K}) \times (0.693147) = 2.871 \times 10^{-21}\ \text{J}$$

**Empirical verification:**

| Experiment | System | Result | Source |
|---|---|---|---|
| Bérut et al. | Colloidal particle in optical trap | Achieved (1.6 ± 0.5) kT ln(2) | Nature 483, 187 (2012) |
| Jun et al. | Colloidal particle (feedback trap) | Approached limit at slow erasure rates | Phys. Rev. Lett. 113, 190601 (2014) |
| Hong et al. | Nanomagnetic bit | Confirmed kT ln(2) scaling | Science Advances 2, e1501492 (2016) |

**Note on Bérut et al.:** The measured value of 1.6 kT ln(2) represents the first experimental demonstration that erasure can approach the Landauer limit. The 60% overhead above the theoretical minimum reflects practical implementation constraints, not a violation of the limit. Jun et al. subsequently achieved tighter approach to the bound.

No sub-Landauer erasure has been observed.

**Scope clarification:**

- **Applies to:** Irreversible logical operations (erasure, overwriting, hashing, state finalization)
- **Does not apply to:** Logically reversible computation (theoretically zero minimum energy)
- **Practical note:** Real systems operate far above the Landauer limit due to engineering constraints. Current CMOS logic dissipates ~10⁶ kT per operation.

**Implication for protocols:** Any protocol operation that destroys information requires energy proportional to information destroyed. The total irreversible computation performable by any physical system is bounded by its available free energy. An adversary with energy budget E at temperature T can perform at most E / (kT ln 2) irreversible bit operations.

-----

## L-1.4 Maximum Information Propagation Speed

**Constraint:** No information propagates faster than c = 299,792,458 m/s in vacuum.

**Formal basis:** Special relativity (Lorentz invariance of physical laws). The speed c is the invariant spacetime interval conversion factor; information traveling faster than c would violate causality in some reference frames.

**Empirical status:**

| Test type | Precision | Source |
|---|---|---|
| Michelson-Morley type (isotropy) | Δc/c < 10⁻¹⁷ | Herrmann et al., 2009 |
| Time dilation (muon lifetime) | Confirmed to 0.1% | Bailey et al., 1977 |
| GPS clock synchronization | Continuous verification | Operational since 1978 |
| Neutrino velocity (OPERA, corrected) | \|v − c\|/c < 2 × 10⁻⁵ | ICARUS Collaboration, 2012 |

**Note on OPERA:** The initial OPERA result (2011) suggesting superluminal neutrinos was traced to a loose fiber optic cable and clock synchronization error. Subsequent measurements by ICARUS, OPERA (corrected), LVD, and Borexino all found neutrino velocity consistent with c.

**Note on SI definition:** Since 1983, the meter is defined as the distance light travels in 1/299,792,458 seconds. The value of c is exact by definition; what is tested is the invariance of light speed across reference frames and directions.

**Clarification on "faster-than-light" phenomena:**

- **Phase velocity:** Can exceed c; carries no information
- **Group velocity:** Can exceed c in anomalous dispersion; signal velocity remains ≤ c
- **Quantum entanglement:** No usable information transmitted; correlation only
- **Alcubierre metric:** Requires negative energy density; not physically realized

**Implication for protocols:** Communication over distance d requires time ≥ d/c. For Earth-scale distances:

| Distance | Minimum latency |
|---|---|
| 1 km | 3.34 μs |
| Earth diameter (12,742 km) | 42.5 ms |
| Earth circumference (40,075 km) | 133.7 ms |
| Earth-Moon | 1.28 s |
| Earth-Mars (closest) | 3.0 min |

Simultaneity is frame-dependent (relativity of simultaneity). Instantaneous global state agreement is physically impossible. Any consensus protocol must account for propagation delays.

-----

## L-1.5 Terrestrial Proper Time Uniformity

**Constraint:** For observers on Earth's surface with altitude difference ΔH < 20 km and relative velocity Δv < 1 km/s, proper time rates differ by less than 10⁻¹¹.

**Formal basis:** General relativity (gravitational time dilation) and special relativity (kinematic time dilation).

### Gravitational Time Dilation

**Weak-field approximation (constant g):**

$$\frac{\Delta\tau}{\tau} = \frac{g \cdot \Delta H}{c^2}$$

**Note on approximation validity:** Using constant g = 9.80665 m/s² introduces error because gravitational acceleration varies with altitude as:

$$g(h) = g_0 \left(\frac{R_E}{R_E + h}\right)^2$$

At h = 20 km: g(20 km) ≈ 9.745 m/s², approximately 0.6% lower than surface value. For the precision required here (order-of-magnitude bound), the constant-g approximation is adequate. For sub-percent precision, the integral formulation should be used:

$$\frac{\Delta\tau}{\tau} = \frac{GM}{c^2}\left(\frac{1}{R_E} - \frac{1}{R_E + \Delta H}\right)$$

**Constants used:**

- g = 9.80665 m/s² (standard gravity, defined constant)
- c = 299,792,458 m/s (exact by SI definition)
- c² = 8.987551787368176 × 10¹⁶ m²/s²

**Per-meter coefficient (at Earth's surface):**

$$\frac{\Delta\tau}{\tau \cdot \Delta H} = \frac{9.80665}{8.987551787 \times 10^{16}} = 1.0913 \times 10^{-16}\ \text{m}^{-1}$$

**At ΔH = 20 km (using constant-g approximation):**

$$\frac{\Delta\tau}{\tau} = 1.0913 \times 10^{-16} \times 2 \times 10^{4} = 2.183 \times 10^{-12}$$

**Experimental verification:**

| Experiment | Configuration | Result | Source |
|---|---|---|---|
| Pound-Rebka | 22.5 m tower | (0.997 ± 0.076) × predicted | Phys. Rev. Lett. 4, 337 (1960) |
| Pound-Snider | 22.5 m tower | (1.04 ± 0.10) × predicted | Phys. Rev. 140, B788 (1965) |
| Chou et al. | 33 cm height | Detected at 10⁻¹⁷ level | Science 329, 1630 (2010) |
| Bothwell et al. | mm-scale | Resolved within single clock | Nature 602, 420 (2022) |

**Note on Pound-Snider:** The measured fractional frequency shift was (2.57 ± 0.26) × 10⁻¹⁵, compared to predicted 2.46 × 10⁻¹⁵. The ratio 1.04 ± 0.10 indicates agreement within experimental uncertainties.

### Kinematic Time Dilation

**Low-velocity approximation (v ≪ c):**

$$\frac{\Delta\tau}{\tau} = \frac{v^2}{2c^2}$$

**At Δv = 1 km/s = 1000 m/s:**

$$\frac{\Delta\tau}{\tau} = \frac{(10^3)^2}{2 \times 8.987551787 \times 10^{16}} = \frac{10^6}{1.7975 \times 10^{17}} = 5.563 \times 10^{-12}$$

**Experimental verification:**

| Experiment | Configuration | Result | Source |
|---|---|---|---|
| Hafele-Keating | Circumnavigating aircraft | Confirmed to ~10% | Science 177, 166 (1972) |
| GPS satellites | v ≈ 3.87 km/s | Continuous verification | Operational |
| Particle accelerators | v → c | Time dilation confirmed to < 0.1% | Multiple facilities |

### Combined Bounds

**Extreme terrestrial conditions (ΔH = 20 km, Δv = 1 km/s):**

$$\left|\frac{\Delta\tau}{\tau}\right|_{\max} \leq 2.183 \times 10^{-12} + 5.563 \times 10^{-12} = 7.746 \times 10^{-12} < 10^{-11}$$

**Typical terrestrial nodes (ΔH < 1 km, Δv < 100 m/s):**

| Effect | Value |
|---|---|
| Gravitational | 1.091 × 10⁻¹⁶ × 10³ = 1.091 × 10⁻¹³ |
| Kinematic | (100)² / (2 × 8.988 × 10¹⁶) = 5.56 × 10⁻¹⁴ |
| **Combined** | **1.65 × 10⁻¹³** |

**GPS system verification:** GPS satellites (altitude 20,200 km, velocity 3.87 km/s) experience:

- Gravitational effect: +45.85 μs/day (higher altitude → faster clocks)
- Kinematic effect: −7.21 μs/day (orbital velocity → slower clocks)
- Net correction: +38.64 μs/day

Ground receivers achieve nanosecond-level timing accuracy, confirming relativistic predictions to fractional accuracy < 10⁻¹³.

**Implication for protocols:** Earth-based protocol participants measure elapsed durations at rates indistinguishable for practical synchronization requirements:

| Requirement | Achievable without relativistic corrections | With corrections |
|---|---|---|
| Millisecond | Yes (error < 1 ms over 10⁸ s) | — |
| Microsecond | Yes (error < 1 μs over 10⁵ s) | — |
| Nanosecond | No | Yes |
| Sub-nanosecond | No | Yes (with local clock characterization) |

-----

## L-1.6 Bekenstein Bound

**Constraint:** The maximum information content of a region of space is bounded by its surface area, not its volume.

**Formal statement:** A system of energy E enclosed in a sphere of radius R can contain at most:

$$I_{\max} = \frac{2\pi R E}{\hbar c \ln 2}\ \text{bits}$$

**Derivation:** Bekenstein (1981) showed that exceeding this bound would allow violations of the generalized second law of thermodynamics (including black hole entropy).

**Quantitative example:** For a 1 kg mass in a 1 m radius sphere:

$$I_{\max} = \frac{2\pi \times 1\ \text{m} \times (1\ \text{kg} \times c^2)}{(1.055 \times 10^{-34}\ \text{J·s}) \times (3 \times 10^8\ \text{m/s}) \times 0.693}$$

$$I_{\max} \approx 2.6 \times 10^{43}\ \text{bits}$$

**Empirical status:** No direct test exists (the bound is ~10²⁰ times higher than achievable storage density). However, the bound is derived from black hole thermodynamics, which has indirect support from:
- Consistency of Hawking radiation calculations
- AdS/CFT correspondence results
- No observed violations of generalized second law

**Implication for protocols:** Any finite physical system has finite information capacity. There is no physical substrate for "infinite" computation or storage. This provides an ultimate bound on adversary capabilities independent of technology.

-----

## L-1.7 Thermal Noise Floor

**Constraint:** Any measurement at temperature T has fundamental noise power spectral density of at least kT per unit bandwidth.

**Formal basis:** Johnson-Nyquist theorem (1928). Thermal fluctuations in any resistive element produce voltage noise with power spectral density:

$$S_V = 4 k_B T R\ \text{V}^2/\text{Hz}$$

**Generalized form (fluctuation-dissipation theorem):** Any system coupled to a thermal bath at temperature T exhibits fluctuations with energy scale kT per degree of freedom.

**Value at T = 300 K:**

$$k_B T = 4.14 \times 10^{-21}\ \text{J} = 25.9\ \text{meV}$$

**Implications for measurement precision:**

| Measurement type | Thermal limit at 300 K |
|---|---|
| Voltage (1 kΩ, 1 Hz BW) | 4.1 nV/√Hz |
| Position (optical trap) | ~nm scale |
| Timing (electronic) | ~ps scale (with averaging) |

**Empirical status:** Confirmed in countless experiments since 1928. The fluctuation-dissipation theorem is a cornerstone of statistical mechanics.

**Implication for protocols:** Physical measurements have fundamental precision limits. Any protocol relying on analog measurements must account for thermal noise. This constrains side-channel attack precision and physical random number generation.

-----

## L-1.8 Quantum Decoherence

**Constraint:** Quantum superpositions of macroscopically distinguishable states decohere on timescales inversely proportional to environmental coupling strength.

**Formal basis:** Quantum mechanics + environmental interaction. A quantum system in superposition |ψ⟩ = α|0⟩ + β|1⟩ interacting with an environment undergoes:

$$\rho(t) = |\alpha|^2|0⟩⟨0| + |\beta|^2|1⟩⟨1| + (\alpha\beta^* e^{-t/\tau_d}|0⟩⟨1| + \text{h.c.})$$

where τ_d is the decoherence time.

**Decoherence timescales (order of magnitude):**

| System | Environment | τ_d |
|---|---|---|
| Superconducting qubit | Dilution fridge (10 mK) | ~100 μs |
| Trapped ion | Ultra-high vacuum | ~1 s |
| Electron spin (diamond NV) | Room temperature | ~ms |
| Large molecule (C₆₀) | Vacuum, thermal | ~ns |
| Dust grain (10 μm) | Air, room temp | ~10⁻³⁶ s (for Δx ~ 1 cm) |
| Cat (superposition) | Any environment | < 10⁻⁴⁰ s |

**Empirical status:** Decoherence rates match theoretical predictions across many orders of magnitude. Interference experiments confirm loss of coherence at predicted rates.

**Implication for protocols:**
1. Macroscopic superpositions do not persist—classical definiteness emerges naturally
2. Quantum computers require active error correction to maintain coherence
3. "Quantum" attacks on protocols are constrained by decoherence timescales
4. This provides physical grounding for treating macroscopic states as definite

-----

## L-1.9 Explicit Exclusions

This layer excludes by design:

| Excluded | Reason | Belongs to |
|---|---|---|
| Computational hardness assumptions (P ≠ NP, factoring, discrete log) | Not physical laws; depend on mathematical conjectures | Cryptographic layers |
| Specific hash functions, signature schemes, encryption algorithms | Design choices | Protocol specification |
| Network topology, latency distributions, node behavior | Implementation-dependent | System model layers |
| Security definitions (unforgeability, confidentiality, etc.) | Derived from physical + computational assumptions | Higher layers |
| Quantum computing capabilities | Technology-dependent, not physical limit | Adversary model layers |

-----

## L-1.10 Classification of Constraints

| ID | Constraint | Type | Confidence | Violation would require |
|---|---|---|---|---|
| L-1.1 | Thermodynamic arrow | Fundamental statistical law | No macroscopic exception in 150+ years | New physics at macroscopic scales; would invalidate statistical mechanics |
| L-1.2 | Atomic time reproducibility | Empirical regularity from QM | Reproducible to 10⁻¹⁸ | Variation in fundamental constants; would invalidate QED |
| L-1.3 | Landauer limit | Theorem (given stat. mech.) | Experimentally approached at slow rates | Violation of second law or information-entropy equivalence |
| L-1.4 | Speed of light limit | Fundamental spacetime structure | Isotropy tested to 10⁻¹⁷ | Lorentz invariance breakdown; would invalidate special relativity |
| L-1.5 | Terrestrial time uniformity | Derived from L-1.4 + GR | Continuously verified (GPS, optical clocks) | General relativity failure at weak-field limit |
| L-1.6 | Bekenstein bound | Theorem (given GR + QM) | Indirect (black hole thermodynamics) | Violation of generalized second law |
| L-1.7 | Thermal noise floor | Theorem (given stat. mech.) | Confirmed since 1928 | Violation of fluctuation-dissipation theorem |
| L-1.8 | Quantum decoherence | Derived from QM + environment | Confirmed across many systems | Failure of quantum mechanics or thermodynamics |

-----

## L-1.11 Adversary Model Boundaries

**Explicit assumption:** The adversary has arbitrarily large but finite physical resources, bounded by physics.

**Clarification on "unbounded":** We do not assume the adversary is literally computationally unbounded—this would contradict L-1.3 (Landauer) and L-1.6 (Bekenstein). Instead, we assume:

1. The adversary's computational resources may be arbitrarily large but are finite
2. We place no specific bound on these resources (no assumption like "adversary has at most 2⁸⁰ operations")
3. The adversary is constrained only by physical law, not by technology or economics

This formulation avoids the logical contradiction between "unbounded computation" and thermodynamic limits while preserving the intent: protocols should not rely on the adversary having limited computational resources.

**Definition:** The adversary may have arbitrary (but finite) computational resources but cannot:

1. **Reverse macroscopic entropy spontaneously** (violates L-1.1)
   - Cannot un-hash, un-burn, or un-mix macroscopic systems

2. **Build clocks that disagree with atomic standards** (violates L-1.2)
   - Cannot create time measurement devices with systematic bias undetectable by atomic comparison

3. **Erase information without energy dissipation** (violates L-1.3)
   - Total irreversible computation bounded by available energy

4. **Signal faster than light** (violates L-1.4)
   - Cannot coordinate actions across spacelike-separated events
   - Cannot influence the past

5. **Experience proper time at rates differing by >10⁻¹¹ on Earth's surface** under stated conditions (violates L-1.5)
   - Cannot create significant "time pockets" for computational advantage

6. **Store more information than the Bekenstein bound** (violates L-1.6)
   - Finite physical systems have finite information capacity

7. **Measure with precision exceeding thermal limits** without cooling (violates L-1.7)
   - Measurement precision bounded by temperature

8. **Maintain macroscopic quantum superpositions** indefinitely (violates L-1.8)
   - Decoherence limits quantum computational strategies

**Why this assumption is necessary:** Without it, "security" is undefined.

- An adversary who can violate thermodynamics can reverse any computation, including cryptographic hash functions at the physical level.
- An adversary who can signal superluminally can violate causality, making temporal ordering undefined.
- An adversary who can exceed the Bekenstein bound has access to infinite information storage.

Such an adversary could also violate the mathematical axioms underlying any cryptographic scheme (by simulating any mathematical structure with arbitrary precision using unbounded resources). Defense against physics violations is not a meaningful security goal.

**Why this assumption is minimal:** We assume only experimentally-verified physics at macroscopic scales. We do not assume:

- P ≠ NP
- One-way functions exist
- Any specific cryptographic primitive is secure
- Any specific bound on adversary's computational resources
- Any bound on adversary's mathematical sophistication

These stronger assumptions belong to higher layers and carry higher uncertainty.

**Relationship to computational assumptions:** Layer -1 provides the foundation; computational security is layered on top. A protocol proven secure under computational assumptions inherits Layer -1 constraints implicitly. Making them explicit clarifies that:

1. Security proofs assume physics holds
2. Physical attacks (side channels, timing, power analysis) are in scope
3. Relativistic and thermodynamic constraints can be leveraged for security

-----

## L-1.12 Verification Criteria

Each constraint in L-1.1–L-1.8 satisfies:

| Criterion | Requirement | L-1.1 | L-1.2 | L-1.3 | L-1.4 | L-1.5 | L-1.6 | L-1.7 | L-1.8 |
|---|---|---|---|---|---|---|---|---|---|
| Empirical basis | Experimentally tested | ✓ | ✓ | ✓ | ✓ | ✓ | ○ | ✓ | ✓ |
| Quantified precision | Uncertainty bounds stated | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Independent verification | Confirmed by multiple groups | ✓ | ✓ | ✓ | ✓ | ✓ | ○ | ✓ | ✓ |
| No circularity | Does not assume conclusion | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Protocol independence | Applies regardless of design | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Explicit scope | Domain of applicability stated | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

**Legend:** ✓ = fully satisfied, ○ = satisfied indirectly (theoretical derivation from tested principles)

-----

## L-1.13 Statement of Confidence

Layer -1 is not a claim of metaphysical certainty. It is a claim of **maximal empirical confidence**:

1. **Relative confidence:** These constraints have been tested more rigorously than any cryptographic assumption. The weakest constraint (Bekenstein bound, L-1.6) has only indirect support; the strongest (speed of light, L-1.4) has been tested to 10⁻¹⁷.

2. **Scale of validity:** These laws successfully predict phenomena across:
   - Length scales: 10⁻¹⁸ m (particle physics) to 10²⁶ m (cosmology)
   - Time scales: 10⁻²⁴ s (particle interactions) to 10¹⁷ s (age of universe)
   - Energy scales: 10⁻³² J (atomic transitions) to 10⁴⁴ J (supernovae)

3. **Failure mode:** Violation at protocol-relevant scales (meters, seconds, joules) would require revision of physics that has no observed failure at any tested scale. This is not impossible, but represents the highest confidence level achievable through empirical science.

4. **Implicit assumption:** Any protocol implicitly assumes these constraints. A protocol that assumes computational hardness already assumes physics (computation requires physical substrate). Layer -1 makes this assumption explicit.

**Inherited constraints:** A protocol built on Layer -1 inherits no additional physical assumptions. Its security reduces entirely to:

- Computational assumptions (Layer 0+)
- Mathematical assumptions (set theory, logic)
- Protocol-specific assumptions (stated in higher layers)

-----

## L-1.14 References

### Foundational Physics

- Einstein, A. (1905). "Zur Elektrodynamik bewegter Körper." *Annalen der Physik* 322(10): 891–921.
- Einstein, A. (1915). "Die Feldgleichungen der Gravitation." *Sitzungsberichte der Preussischen Akademie der Wissenschaften*: 844–847.
- Landauer, R. (1961). "Irreversibility and Heat Generation in the Computing Process." *IBM Journal of Research and Development* 5(3): 183–191.
- Bennett, C.H. (1982). "The thermodynamics of computation—a review." *International Journal of Theoretical Physics* 21(12): 905–940.
- Bekenstein, J.D. (1981). "Universal upper bound on the entropy-to-energy ratio for bounded systems." *Physical Review D* 23(2): 287–298.
- Johnson, J.B. (1928). "Thermal Agitation of Electricity in Conductors." *Physical Review* 32(1): 97–109.
- Nyquist, H. (1928). "Thermal Agitation of Electric Charge in Conductors." *Physical Review* 32(1): 110–113.
- Zurek, W.H. (2003). "Decoherence, einselection, and the quantum origins of the classical." *Reviews of Modern Physics* 75(3): 715–775.

### Experimental Verification

- Pound, R.V. & Rebka, G.A. (1960). "Apparent Weight of Photons." *Physical Review Letters* 4(7): 337–341.
- Pound, R.V. & Snider, J.L. (1965). "Effect of Gravity on Gamma Radiation." *Physical Review* 140(4B): B788–B803.
- Hafele, J.C. & Keating, R.E. (1972). "Around-the-World Atomic Clocks." *Science* 177(4044): 166–170.
- Bérut, A. et al. (2012). "Experimental verification of Landauer's principle." *Nature* 483: 187–189.
- Jun, Y., Gavrilov, M. & Bechhoefer, J. (2014). "High-Precision Test of Landauer's Principle in a Feedback Trap." *Physical Review Letters* 113(19): 190601.
- Hong, J. et al. (2016). "Experimental test of Landauer's principle in single-bit operations on nanomagnetic memory bits." *Science Advances* 2(3): e1501492.
- Chou, C.W. et al. (2010). "Optical Clocks and Relativity." *Science* 329(5999): 1630–1633.
- Herrmann, S. et al. (2009). "Rotating optical cavity experiment testing Lorentz invariance at the 10⁻¹⁷ level." *Physical Review D* 80(10): 105011.
- McGrew, W.F. et al. (2018). "Atomic clock performance enabling geodesy below the centimetre level." *Nature* 564: 87–90.
- Bothwell, T. et al. (2022). "Resolving the gravitational redshift across a millimetre-scale atomic sample." *Nature* 602: 420–424.
- Brewer, S.M. et al. (2019). "²⁷Al⁺ Quantum-Logic Clock with a Systematic Uncertainty below 10⁻¹⁸." *Physical Review Letters* 123(3): 033201.
- Rosenband, T. et al. (2008). "Frequency Ratio of Al⁺ and Hg⁺ Single-Ion Optical Clocks; Metrology at the 17th Decimal Place." *Science* 319(5871): 1808–1812.
- Evans, D.J., Cohen, E.G.D. & Morriss, G.P. (1993). "Probability of second law violations in shearing steady states." *Physical Review Letters* 71(15): 2401–2404.
- Wang, G.M. et al. (2002). "Experimental Demonstration of Violations of the Second Law of Thermodynamics for Small Systems and Short Time Scales." *Physical Review Letters* 89(5): 050601.
- Bailey, J. et al. (1977). "Measurements of relativistic time dilatation for positive and negative muons in a circular orbit." *Nature* 268: 301–305.
- Antonello, M. et al. [ICARUS Collaboration] (2012). "Measurement of the neutrino velocity with the ICARUS detector at the CNGS beam." *Physics Letters B* 713(1): 17–22.
- Joos, E. & Zeh, H.D. (1985). "The emergence of classical properties through interaction with the environment." *Zeitschrift für Physik B* 59(2): 223–243.
- Arndt, M. et al. (1999). "Wave-particle duality of C₆₀ molecules." *Nature* 401: 680–682.

### Metrology Standards

- BIPM. "SI Brochure: The International System of Units (SI)." 9th edition, 2019.
- NIST. "CODATA Recommended Values of the Fundamental Physical Constants: 2018."

-----

*Layer -1 represents the boundary conditions imposed by physical law on any information-processing system. Protocols may assume weaker physics (additional constraints); they cannot assume stronger physics (fewer constraints) without leaving the domain of known science.*
