//! One-shot ML-DSA (Dilithium3) signer for Genesis Identity payloads.
//!
//! Reads message bytes from STDIN and outputs:
//! - pubkey_hex=...
//! - signature_hex=...
//! - secret_hex=...
//!
//! Intended usage (Python bot):
//!   genesis_sign < genesis_payload.bin

use pqcrypto_dilithium::dilithium3 as mldsa;
use pqcrypto_traits::sign::{DetachedSignature as _, PublicKey as _, SecretKey as _};
use std::io::{self, Read};

fn main() {
    let mut message = Vec::new();
    io::stdin()
        .read_to_end(&mut message)
        .expect("failed to read message from stdin");

    if message.is_empty() {
        eprintln!("error: empty message (stdin). Refusing to sign.");
        std::process::exit(2);
    }

    let (pk, sk) = mldsa::keypair();
    let sig = mldsa::detached_sign(&message, &sk);

    println!("pubkey_hex={}", hex::encode(pk.as_bytes()));
    println!("signature_hex={}", hex::encode(sig.as_bytes()));
    println!("secret_hex={}", hex::encode(sk.as_bytes()));
}



