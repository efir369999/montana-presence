"""
PoT Protocol v6 Account Management
Part XV of Technical Specification

Account state management and queries.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Iterator, Tuple

from pot.constants import (
    SCORE_MIN_HEARTBEATS,
    ACTIVITY_WINDOW_BLOCKS,
)
from pot.core.types import Hash, PublicKey
from pot.core.state import AccountState
from pot.consensus.score import compute_score, effective_score

logger = logging.getLogger(__name__)


@dataclass
class AccountManager:
    """
    Manages account state with efficient lookup and updates.

    Provides methods for:
    - Account CRUD operations
    - Balance queries
    - Activity tracking
    - Score calculations
    """
    _accounts: Dict[bytes, AccountState] = field(default_factory=dict)
    _active_count: int = 0
    _total_balance: int = 0

    def get(self, pubkey: PublicKey) -> Optional[AccountState]:
        """Get account by public key."""
        return self._accounts.get(pubkey.data)

    def get_or_create(self, pubkey: PublicKey) -> AccountState:
        """Get account or create if not exists."""
        if pubkey.data not in self._accounts:
            account = AccountState(pubkey=pubkey)
            self._accounts[pubkey.data] = account
            self._active_count += 1
            return account
        return self._accounts[pubkey.data]

    def set(self, pubkey: PublicKey, account: AccountState) -> None:
        """Set account state."""
        is_new = pubkey.data not in self._accounts
        old_balance = 0 if is_new else self._accounts[pubkey.data].balance

        self._accounts[pubkey.data] = account
        self._total_balance += (account.balance - old_balance)

        if is_new:
            self._active_count += 1

    def delete(self, pubkey: PublicKey) -> bool:
        """Delete account (rarely used)."""
        if pubkey.data in self._accounts:
            account = self._accounts.pop(pubkey.data)
            self._total_balance -= account.balance
            self._active_count -= 1
            return True
        return False

    def exists(self, pubkey: PublicKey) -> bool:
        """Check if account exists."""
        return pubkey.data in self._accounts

    def get_balance(self, pubkey: PublicKey) -> int:
        """Get balance for public key."""
        account = self.get(pubkey)
        return account.balance if account else 0

    def get_nonce(self, pubkey: PublicKey) -> int:
        """Get nonce for public key."""
        account = self.get(pubkey)
        return account.nonce if account else 0

    def get_epoch_heartbeats(self, pubkey: PublicKey) -> int:
        """Get epoch heartbeat count."""
        account = self.get(pubkey)
        return account.epoch_heartbeats if account else 0

    def get_total_heartbeats(self, pubkey: PublicKey) -> int:
        """Get total heartbeat count."""
        account = self.get(pubkey)
        return account.total_heartbeats if account else 0

    def get_score(self, pubkey: PublicKey) -> float:
        """Get raw score for account."""
        account = self.get(pubkey)
        if account is None:
            return 0.0
        return compute_score(account.epoch_heartbeats)

    def transfer(
        self,
        sender: PublicKey,
        receiver: PublicKey,
        amount: int
    ) -> bool:
        """
        Transfer balance between accounts.

        Args:
            sender: Sender public key
            receiver: Receiver public key
            amount: Amount to transfer

        Returns:
            True if transfer succeeded
        """
        sender_account = self.get(sender)
        if sender_account is None:
            logger.debug(f"Transfer failed: sender not found")
            return False

        if sender_account.balance < amount:
            logger.debug(f"Transfer failed: insufficient balance")
            return False

        receiver_account = self.get_or_create(receiver)

        sender_account.balance -= amount
        receiver_account.balance += amount

        self.set(sender, sender_account)
        self.set(receiver, receiver_account)

        return True

    def credit(self, pubkey: PublicKey, amount: int) -> None:
        """Credit amount to account (creates if needed)."""
        account = self.get_or_create(pubkey)
        account.balance += amount
        self.set(pubkey, account)

    def debit(self, pubkey: PublicKey, amount: int) -> bool:
        """
        Debit amount from account.

        Returns:
            True if debit succeeded
        """
        account = self.get(pubkey)
        if account is None or account.balance < amount:
            return False

        account.balance -= amount
        self.set(pubkey, account)
        return True

    def increment_heartbeat(
        self,
        pubkey: PublicKey,
        block_height: int
    ) -> AccountState:
        """Increment heartbeat counts for account."""
        account = self.get_or_create(pubkey)
        account.epoch_heartbeats += 1
        account.total_heartbeats += 1
        account.last_heartbeat_height = block_height
        self.set(pubkey, account)
        return account

    def increment_nonce(self, pubkey: PublicKey) -> int:
        """Increment nonce and return new value."""
        account = self.get(pubkey)
        if account is None:
            return 0
        account.nonce += 1
        self.set(pubkey, account)
        return account.nonce

    def reset_epoch_counters(self) -> None:
        """Reset epoch counters for all accounts."""
        for account in self._accounts.values():
            account.epoch_heartbeats = 0
            account.epoch_tx_count = 0

    def get_all_pubkeys(self) -> List[PublicKey]:
        """Get list of all public keys."""
        return [PublicKey(pk_bytes) for pk_bytes in self._accounts.keys()]

    def iterate_accounts(self) -> Iterator[AccountState]:
        """Iterate over all accounts."""
        return iter(self._accounts.values())

    def get_active_accounts(self, current_height: int) -> List[AccountState]:
        """
        Get accounts that are currently active.

        Active = heartbeat within ACTIVITY_WINDOW_BLOCKS
        """
        active = []
        for account in self._accounts.values():
            if current_height - account.last_heartbeat_height <= ACTIVITY_WINDOW_BLOCKS:
                active.append(account)
        return active

    def get_eligible_signers(
        self,
        current_height: int,
        min_heartbeats: int = SCORE_MIN_HEARTBEATS
    ) -> List[AccountState]:
        """
        Get accounts eligible to sign blocks.

        Criteria:
        - At least min_heartbeats in current epoch
        - Active within activity window
        """
        eligible = []
        for account in self._accounts.values():
            if account.epoch_heartbeats < min_heartbeats:
                continue

            if current_height - account.last_heartbeat_height > ACTIVITY_WINDOW_BLOCKS:
                continue

            eligible.append(account)

        return eligible

    def get_top_by_score(
        self,
        limit: int = 100,
        current_height: Optional[int] = None
    ) -> List[Tuple[AccountState, float]]:
        """
        Get top accounts by score.

        Args:
            limit: Maximum number to return
            current_height: For activity calculation

        Returns:
            List of (account, score) tuples
        """
        scored = []
        for account in self._accounts.values():
            score = compute_score(account.epoch_heartbeats)
            if score > 0:
                scored.append((account, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def get_rich_list(self, limit: int = 100) -> List[Tuple[AccountState, int]]:
        """
        Get top accounts by balance.

        Returns:
            List of (account, balance) tuples
        """
        rich = []
        for account in self._accounts.values():
            if account.balance > 0:
                rich.append((account, account.balance))

        rich.sort(key=lambda x: x[1], reverse=True)
        return rich[:limit]

    def count(self) -> int:
        """Get total number of accounts."""
        return self._active_count

    def total_balance(self) -> int:
        """Get total balance across all accounts."""
        return self._total_balance

    def total_heartbeats(self) -> int:
        """Get total heartbeats across all accounts."""
        return sum(a.total_heartbeats for a in self._accounts.values())

    def copy(self) -> "AccountManager":
        """Create a deep copy of the account manager."""
        new_manager = AccountManager()
        for pk_bytes, account in self._accounts.items():
            new_manager._accounts[pk_bytes] = AccountState(
                pubkey=account.pubkey,
                balance=account.balance,
                nonce=account.nonce,
                epoch_heartbeats=account.epoch_heartbeats,
                epoch_tx_count=account.epoch_tx_count,
                total_heartbeats=account.total_heartbeats,
                last_heartbeat_height=account.last_heartbeat_height,
                second_tx_count=account.second_tx_count,
                last_tx_second=account.last_tx_second,
            )
        new_manager._active_count = self._active_count
        new_manager._total_balance = self._total_balance
        return new_manager

    def to_dict(self) -> Dict[str, dict]:
        """Export accounts as dictionary."""
        return {
            pk_bytes.hex(): {
                "balance": account.balance,
                "nonce": account.nonce,
                "epoch_heartbeats": account.epoch_heartbeats,
                "total_heartbeats": account.total_heartbeats,
            }
            for pk_bytes, account in self._accounts.items()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, dict]) -> "AccountManager":
        """Import accounts from dictionary."""
        manager = cls()
        for pk_hex, account_data in data.items():
            pk = PublicKey(bytes.fromhex(pk_hex))
            account = AccountState(
                pubkey=pk,
                balance=account_data.get("balance", 0),
                nonce=account_data.get("nonce", 0),
                epoch_heartbeats=account_data.get("epoch_heartbeats", 0),
                total_heartbeats=account_data.get("total_heartbeats", 0),
            )
            manager._accounts[pk.data] = account
            manager._total_balance += account.balance
            manager._active_count += 1
        return manager


def get_account_info() -> dict:
    """Get information about account management."""
    return {
        "fields": [
            "pubkey",
            "balance",
            "nonce",
            "epoch_heartbeats",
            "epoch_tx_count",
            "total_heartbeats",
            "last_heartbeat_height",
            "second_tx_count",
            "last_tx_second",
        ],
        "score_min_heartbeats": SCORE_MIN_HEARTBEATS,
        "activity_window_blocks": ACTIVITY_WINDOW_BLOCKS,
    }
