//! Data Structures for PoT Blockchain
//!
//! Provides:
//! - Block and BlockHeader
//! - Transaction, TxInput, TxOutput
//! - Common types (Hash256, Timestamp, Height)
//!
//! All structures use serde for JSON and bincode for binary serialization.

pub mod block;
pub mod transaction;
pub mod types;

pub use block::{Block, BlockHeader};
pub use transaction::{Transaction, TxInput, TxOutput, TransactionType};
pub use types::{Hash256, Timestamp, Height, Amount};
