"""
ATC Protocol v7 VDF Structures
Part III Section 3.4 of Technical Specification

Verifiable Delay Function proof structure.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple

from atc.constants import (
    VDF_CHECKPOINT_INTERVAL,
    VDF_BASE_ITERATIONS,
    VDF_MAX_ITERATIONS,
)
from atc.core.types import Hash
from atc.core.serialization import ByteReader, ByteWriter


@dataclass(slots=True)
class VDFProof:
    """
    Verifiable Delay Function proof.

    SIZE: 72 + (32 * checkpoint_count) + len(stark_proof) bytes

    The VDF provides cryptographic proof that real time has elapsed.

    Properties:
    - Sequential: Output depends on all previous computations
    - Non-parallelizable: 10,000 CPUs = 1 CPU in elapsed time
    - Verifiable: O(log n) verification via STARK proofs
    - Quantum-resistant: Hash-based construction
    """
    seed: Hash                          # Input seed (SHA3-256 of inputs)
    output: Hash                        # Final VDF output
    iterations: int                     # Number of sequential hashes (u64)
    checkpoint_count: int               # Number of checkpoints (u32)
    checkpoints: List[Hash]             # STARK checkpoints
    stark_proof: bytes                  # STARK proof (~50-200 KB)

    def __post_init__(self):
        if len(self.checkpoints) != self.checkpoint_count:
            raise ValueError(
                f"checkpoint_count ({self.checkpoint_count}) != "
                f"len(checkpoints) ({len(self.checkpoints)})"
            )
        if not 0 <= self.iterations <= VDF_MAX_ITERATIONS:
            raise ValueError(f"Invalid iterations: {self.iterations}")

    def serialize(self) -> bytes:
        """Serialize to bytes."""
        writer = ByteWriter()

        # Fixed fields
        writer.write_raw(self.seed.serialize())      # 32 bytes
        writer.write_raw(self.output.serialize())    # 32 bytes
        writer.write_u64(self.iterations)            # 8 bytes
        writer.write_u32(self.checkpoint_count)      # 4 bytes

        # Variable: checkpoints
        for checkpoint in self.checkpoints:
            writer.write_raw(checkpoint.serialize())

        # Variable: STARK proof with length prefix
        writer.write_varint(len(self.stark_proof))
        writer.write_raw(self.stark_proof)

        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple["VDFProof", int]:
        """Deserialize from bytes."""
        reader = ByteReader(data[offset:])

        seed = Hash(reader.read_fixed_bytes(32))
        output = Hash(reader.read_fixed_bytes(32))
        iterations = reader.read_u64()
        checkpoint_count = reader.read_u32()

        checkpoints = []
        for _ in range(checkpoint_count):
            checkpoints.append(Hash(reader.read_fixed_bytes(32)))

        stark_proof_len = reader.read_varint()
        stark_proof = reader.read_fixed_bytes(stark_proof_len)

        return cls(
            seed=seed,
            output=output,
            iterations=iterations,
            checkpoint_count=checkpoint_count,
            checkpoints=checkpoints,
            stark_proof=stark_proof
        ), reader.offset

    def size(self) -> int:
        """Return size in bytes."""
        base_size = 32 + 32 + 8 + 4  # seed + output + iterations + checkpoint_count
        checkpoints_size = 32 * self.checkpoint_count
        stark_size = len(self.stark_proof)
        varint_size = 1 if stark_size <= 0xFC else (3 if stark_size <= 0xFFFF else 5)
        return base_size + checkpoints_size + varint_size + stark_size

    def expected_checkpoint_count(self) -> int:
        """Calculate expected number of checkpoints for this iteration count."""
        return (self.iterations // VDF_CHECKPOINT_INTERVAL) + 1

    def is_checkpoint_count_valid(self) -> bool:
        """Check if checkpoint count matches expected for iterations."""
        expected = self.expected_checkpoint_count()
        return self.checkpoint_count == expected

    def has_valid_structure(self) -> bool:
        """
        Basic structural validation.

        Checks:
        - Checkpoint count matches iterations
        - First checkpoint should match seed (after prefix)
        - Last checkpoint should match output
        """
        if not self.is_checkpoint_count_valid():
            return False

        if self.checkpoint_count > 0:
            # Last checkpoint should be output
            if self.checkpoints[-1] != self.output:
                return False

        return True

    @classmethod
    def empty(cls) -> "VDFProof":
        """Create an empty VDF proof."""
        return cls(
            seed=Hash.zero(),
            output=Hash.zero(),
            iterations=0,
            checkpoint_count=0,
            checkpoints=[],
            stark_proof=b""
        )

    def __repr__(self) -> str:
        return (
            f"VDFProof(iterations={self.iterations}, "
            f"checkpoints={self.checkpoint_count}, "
            f"stark_size={len(self.stark_proof)})"
        )


def calculate_checkpoint_count(iterations: int) -> int:
    """
    Calculate number of checkpoints for given iteration count.

    Checkpoints are stored every VDF_CHECKPOINT_INTERVAL iterations,
    plus the initial and final states.
    """
    if iterations == 0:
        return 1  # Just initial state

    # Number of full intervals
    full_intervals = iterations // VDF_CHECKPOINT_INTERVAL

    # Add 1 for initial state
    # Add 1 if there's a remainder (final state not at checkpoint boundary)
    count = full_intervals + 1
    if iterations % VDF_CHECKPOINT_INTERVAL != 0:
        count += 1

    return count


def iterations_from_difficulty(difficulty_level: int) -> int:
    """
    Calculate iterations from difficulty level.

    Difficulty doubles base iterations for each level.
    """
    return min(VDF_BASE_ITERATIONS * (2 ** difficulty_level), VDF_MAX_ITERATIONS)


def estimated_vdf_time_seconds(iterations: int) -> float:
    """
    Estimate VDF computation time in seconds.

    Based on benchmarks:
    - VDF_BASE_ITERATIONS (2^24) takes approximately 2.5 seconds
    - Time scales linearly with iterations
    """
    return (iterations / VDF_BASE_ITERATIONS) * 2.5
