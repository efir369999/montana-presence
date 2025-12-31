"""
PoT Protocol v6 Node Configuration
"""

from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

from pot.constants import (
    DEFAULT_PORT,
    NETWORK_ID_MAINNET,
    NETWORK_ID_TESTNET,
)

logger = logging.getLogger(__name__)


@dataclass
class NetworkConfig:
    """Network configuration."""
    listen_address: str = "0.0.0.0"
    listen_port: int = DEFAULT_PORT
    max_peers: int = 50
    max_inbound: int = 25
    bootstrap_nodes: List[str] = field(default_factory=list)
    enable_upnp: bool = False
    external_ip: Optional[str] = None


@dataclass
class StorageConfig:
    """Storage configuration."""
    data_dir: str = "./data"
    db_name: str = "pot_state.db"
    max_block_cache: int = 1000
    max_state_history: int = 100


@dataclass
class MempoolConfig:
    """Mempool configuration."""
    max_heartbeats: int = 10000
    max_transactions: int = 50000
    max_size_bytes: int = 100_000_000  # 100 MB
    eviction_interval_sec: int = 60


@dataclass
class MiningConfig:
    """Mining/heartbeat configuration."""
    enabled: bool = True
    heartbeat_interval_sec: int = 60
    auto_sign_blocks: bool = True


@dataclass
class APIConfig:
    """API server configuration."""
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8545
    cors_origins: List[str] = field(default_factory=list)
    max_batch_size: int = 100


@dataclass
class LogConfig:
    """Logging configuration."""
    level: str = "INFO"
    file: Optional[str] = None
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    max_size_mb: int = 100
    backup_count: int = 5


@dataclass
class NodeConfig:
    """
    Complete node configuration.

    All settings for running a PoT node.
    """
    # Identity
    name: str = "pot-node"
    testnet: bool = False

    # Sub-configurations
    network: NetworkConfig = field(default_factory=NetworkConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    mempool: MempoolConfig = field(default_factory=MempoolConfig)
    mining: MiningConfig = field(default_factory=MiningConfig)
    api: APIConfig = field(default_factory=APIConfig)
    log: LogConfig = field(default_factory=LogConfig)

    # Key paths
    keyfile: Optional[str] = None

    @property
    def network_id(self) -> int:
        """Get network ID based on testnet flag."""
        return NETWORK_ID_TESTNET if self.testnet else NETWORK_ID_MAINNET

    @property
    def data_path(self) -> Path:
        """Get data directory path."""
        return Path(self.storage.data_dir)

    @property
    def db_path(self) -> Path:
        """Get database file path."""
        return self.data_path / self.storage.db_name

    def validate(self) -> List[str]:
        """
        Validate configuration.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Network validation
        if self.network.listen_port < 1 or self.network.listen_port > 65535:
            errors.append(f"Invalid listen port: {self.network.listen_port}")

        if self.network.max_peers < 1:
            errors.append("max_peers must be at least 1")

        # Storage validation
        if not self.storage.data_dir:
            errors.append("data_dir cannot be empty")

        # Mempool validation
        if self.mempool.max_transactions < 100:
            errors.append("max_transactions must be at least 100")

        # API validation
        if self.api.enabled:
            if self.api.port < 1 or self.api.port > 65535:
                errors.append(f"Invalid API port: {self.api.port}")

        return errors

    def save(self, path: str) -> None:
        """Save configuration to file."""
        config_dict = {
            "name": self.name,
            "testnet": self.testnet,
            "keyfile": self.keyfile,
            "network": asdict(self.network),
            "storage": asdict(self.storage),
            "mempool": asdict(self.mempool),
            "mining": asdict(self.mining),
            "api": asdict(self.api),
            "log": asdict(self.log),
        }

        with open(path, 'w') as f:
            json.dump(config_dict, f, indent=2)

        logger.info(f"Configuration saved to {path}")

    @classmethod
    def load(cls, path: str) -> "NodeConfig":
        """Load configuration from file."""
        with open(path, 'r') as f:
            data = json.load(f)

        config = cls(
            name=data.get("name", "pot-node"),
            testnet=data.get("testnet", False),
            keyfile=data.get("keyfile"),
        )

        if "network" in data:
            config.network = NetworkConfig(**data["network"])

        if "storage" in data:
            config.storage = StorageConfig(**data["storage"])

        if "mempool" in data:
            config.mempool = MempoolConfig(**data["mempool"])

        if "mining" in data:
            config.mining = MiningConfig(**data["mining"])

        if "api" in data:
            config.api = APIConfig(**data["api"])

        if "log" in data:
            config.log = LogConfig(**data["log"])

        logger.info(f"Configuration loaded from {path}")
        return config

    @classmethod
    def default_testnet(cls) -> "NodeConfig":
        """Create default testnet configuration."""
        config = cls(
            name="pot-testnet-node",
            testnet=True,
        )

        config.network.listen_port = DEFAULT_PORT + 1
        config.storage.data_dir = "./data-testnet"
        config.api.port = 8546

        config.network.bootstrap_nodes = [
            "testnet1.pot.network:19657",
            "testnet2.pot.network:19657",
        ]

        return config

    @classmethod
    def default_mainnet(cls) -> "NodeConfig":
        """Create default mainnet configuration."""
        config = cls(
            name="pot-mainnet-node",
            testnet=False,
        )

        config.network.bootstrap_nodes = [
            "node1.pot.network:19656",
            "node2.pot.network:19656",
            "node3.pot.network:19656",
        ]

        return config

    def to_dict(self) -> dict:
        """Export configuration as dictionary."""
        return {
            "name": self.name,
            "testnet": self.testnet,
            "network_id": self.network_id,
            "keyfile": self.keyfile,
            "network": asdict(self.network),
            "storage": asdict(self.storage),
            "mempool": asdict(self.mempool),
            "mining": asdict(self.mining),
            "api": asdict(self.api),
            "log": asdict(self.log),
        }


def setup_logging(config: LogConfig) -> None:
    """Configure logging based on config."""
    level = getattr(logging, config.level.upper(), logging.INFO)

    handlers = [logging.StreamHandler()]

    if config.file:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            config.file,
            maxBytes=config.max_size_mb * 1024 * 1024,
            backupCount=config.backup_count,
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=level,
        format=config.format,
        handlers=handlers,
    )


def get_config_info() -> dict:
    """Get information about configuration options."""
    return {
        "default_port": DEFAULT_PORT,
        "default_api_port": 8545,
        "default_max_peers": 50,
        "config_format": "JSON",
    }
