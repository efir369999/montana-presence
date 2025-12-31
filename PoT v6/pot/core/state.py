"""
PoT Protocol v6 State Structures
Part III Section 3.9 and Part XV of Technical Specification

Account and global state management.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Iterator
import copy

from pot.constants import (
    TX_EPOCH_DURATION_SEC,
    ACTIVITY_WINDOW_BLOCKS,
)
from pot.core.types import Hash, PublicKey
from pot.core.serialization import ByteReader, ByteWriter
from pot.crypto.hash import sha3_256


@dataclass
class AccountState:
    """
    State for a single account.

    Per specification (Part III Section 3.9):
    - Identity (pubkey)
    - Balance and nonce
    - Heartbeat tracking
    - Transaction tracking for rate limiting
    """
    # Identity
    pubkey: PublicKey

    # Balance
    balance: int = 0                    # Token balance (atomic units)
    nonce: int = 0                      # Last transaction nonce

    # Heartbeat tracking
    total_heartbeats: int = 0           # Lifetime total
    epoch_heartbeats: int = 0           # Current epoch count
    last_hb_btc_height: int = 0         # BTC height of last heartbeat
    last_hb_atomic_ms: int = 0          # Atomic time of last heartbeat

    # Transaction tracking (for rate limiting)
    epoch_tx_count: int = 0             # Transactions this epoch
    current_second: int = 0             # Current second (atomic time / 1000)
    second_tx_count: int = 0            # Transactions in current second

    def serialize(self) -> bytes:
        """Serialize account state."""
        writer = ByteWriter()

        writer.write_raw(self.pubkey.serialize())
        writer.write_u64(self.balance)
        writer.write_u64(self.nonce)
        writer.write_u64(self.total_heartbeats)
        writer.write_u64(self.epoch_heartbeats)
        writer.write_u64(self.last_hb_btc_height)
        writer.write_u64(self.last_hb_atomic_ms)
        writer.write_u32(self.epoch_tx_count)
        writer.write_u64(self.current_second)
        writer.write_u8(self.second_tx_count)

        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple["AccountState", int]:
        """Deserialize account state."""
        pk_data = data[offset:offset + 33]
        pubkey, _ = PublicKey.deserialize(pk_data)
        offset += 33

        reader = ByteReader(data[offset:])

        balance = reader.read_u64()
        nonce = reader.read_u64()
        total_heartbeats = reader.read_u64()
        epoch_heartbeats = reader.read_u64()
        last_hb_btc_height = reader.read_u64()
        last_hb_atomic_ms = reader.read_u64()
        epoch_tx_count = reader.read_u32()
        current_second = reader.read_u64()
        second_tx_count = reader.read_u8()

        return cls(
            pubkey=pubkey,
            balance=balance,
            nonce=nonce,
            total_heartbeats=total_heartbeats,
            epoch_heartbeats=epoch_heartbeats,
            last_hb_btc_height=last_hb_btc_height,
            last_hb_atomic_ms=last_hb_atomic_ms,
            epoch_tx_count=epoch_tx_count,
            current_second=current_second,
            second_tx_count=second_tx_count
        ), 33 + reader.offset

    def is_active(self, current_btc_height: int) -> bool:
        """Check if account has recent activity (heartbeat within window)."""
        if self.last_hb_btc_height == 0:
            return False
        window_start = current_btc_height - ACTIVITY_WINDOW_BLOCKS
        return self.last_hb_btc_height >= window_start

    def copy(self) -> "AccountState":
        """Create a deep copy of this account state."""
        return AccountState(
            pubkey=self.pubkey,
            balance=self.balance,
            nonce=self.nonce,
            total_heartbeats=self.total_heartbeats,
            epoch_heartbeats=self.epoch_heartbeats,
            last_hb_btc_height=self.last_hb_btc_height,
            last_hb_atomic_ms=self.last_hb_atomic_ms,
            epoch_tx_count=self.epoch_tx_count,
            current_second=self.current_second,
            second_tx_count=self.second_tx_count
        )


@dataclass
class GlobalState:
    """
    Global blockchain state.

    Per specification (Part III Section 3.9):
    - Current chain state
    - Bitcoin state
    - Network statistics
    - Account states
    """
    # Current chain state
    chain_height: int = 0
    chain_tip_hash: Hash = field(default_factory=Hash.zero)

    # Bitcoin state
    btc_height: int = 0
    btc_hash: Hash = field(default_factory=Hash.zero)
    btc_epoch: int = 0                  # Current halving epoch

    # Network statistics
    total_supply: int = 0
    total_heartbeats: int = 0
    active_accounts: int = 0            # Accounts with recent activity

    # Account states
    _accounts: Dict[bytes, AccountState] = field(default_factory=dict)

    def get_account(self, pubkey: PublicKey) -> Optional[AccountState]:
        """Get account state by public key."""
        return self._accounts.get(pubkey.data)

    def get_or_create_account(self, pubkey: PublicKey) -> AccountState:
        """Get or create account state."""
        key = pubkey.data
        if key not in self._accounts:
            self._accounts[key] = AccountState(pubkey=pubkey)
        return self._accounts[key]

    def set_account(self, account: AccountState):
        """Set account state."""
        self._accounts[account.pubkey.data] = account

    def has_account(self, pubkey: PublicKey) -> bool:
        """Check if account exists."""
        return pubkey.data in self._accounts

    def iter_accounts(self) -> Iterator[AccountState]:
        """Iterate over all accounts."""
        return iter(self._accounts.values())

    def account_count(self) -> int:
        """Return number of accounts."""
        return len(self._accounts)

    def compute_state_root(self) -> Hash:
        """
        Compute Merkle root of all account states.

        Accounts are sorted by public key for deterministic ordering.
        """
        from pot.crypto.merkle import merkle_root

        if not self._accounts:
            return Hash.zero()

        # Sort accounts by public key
        sorted_accounts = sorted(self._accounts.items(), key=lambda x: x[0])

        # Hash each account state
        account_hashes = [
            sha3_256(account.serialize())
            for _, account in sorted_accounts
        ]

        return merkle_root(account_hashes)

    def copy(self) -> "GlobalState":
        """Create a deep copy of this state."""
        new_state = GlobalState(
            chain_height=self.chain_height,
            chain_tip_hash=self.chain_tip_hash,
            btc_height=self.btc_height,
            btc_hash=self.btc_hash,
            btc_epoch=self.btc_epoch,
            total_supply=self.total_supply,
            total_heartbeats=self.total_heartbeats,
            active_accounts=self.active_accounts
        )

        for key, account in self._accounts.items():
            new_state._accounts[key] = account.copy()

        return new_state

    def serialize(self) -> bytes:
        """Serialize global state."""
        writer = ByteWriter()

        # Chain state
        writer.write_u64(self.chain_height)
        writer.write_raw(self.chain_tip_hash.serialize())

        # Bitcoin state
        writer.write_u64(self.btc_height)
        writer.write_raw(self.btc_hash.serialize())
        writer.write_u32(self.btc_epoch)

        # Statistics
        writer.write_u64(self.total_supply)
        writer.write_u64(self.total_heartbeats)
        writer.write_u64(self.active_accounts)

        # Account count
        writer.write_varint(len(self._accounts))

        # Accounts (sorted for determinism)
        for key in sorted(self._accounts.keys()):
            account = self._accounts[key]
            writer.write_raw(account.serialize())

        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple["GlobalState", int]:
        """Deserialize global state."""
        reader = ByteReader(data[offset:])

        # Chain state
        chain_height = reader.read_u64()
        chain_tip_hash = Hash(reader.read_fixed_bytes(32))

        # Bitcoin state
        btc_height = reader.read_u64()
        btc_hash = Hash(reader.read_fixed_bytes(32))
        btc_epoch = reader.read_u32()

        # Statistics
        total_supply = reader.read_u64()
        total_heartbeats = reader.read_u64()
        active_accounts = reader.read_u64()

        # Accounts
        account_count = reader.read_varint()
        accounts: Dict[bytes, AccountState] = {}

        remaining = data[offset + reader.offset:]
        acc_offset = 0
        for _ in range(account_count):
            account, consumed = AccountState.deserialize(remaining, acc_offset)
            accounts[account.pubkey.data] = account
            acc_offset += consumed

        state = cls(
            chain_height=chain_height,
            chain_tip_hash=chain_tip_hash,
            btc_height=btc_height,
            btc_hash=btc_hash,
            btc_epoch=btc_epoch,
            total_supply=total_supply,
            total_heartbeats=total_heartbeats,
            active_accounts=active_accounts
        )
        state._accounts = accounts

        return state, reader.offset + acc_offset

    def update_active_count(self, current_btc_height: int):
        """Update count of active accounts."""
        count = sum(
            1 for account in self._accounts.values()
            if account.is_active(current_btc_height)
        )
        self.active_accounts = count

    @classmethod
    def empty(cls) -> "GlobalState":
        """Create an empty global state."""
        return cls()

    def __repr__(self) -> str:
        return (
            f"GlobalState(height={self.chain_height}, "
            f"btc_height={self.btc_height}, "
            f"accounts={len(self._accounts)}, "
            f"supply={self.total_supply})"
        )
