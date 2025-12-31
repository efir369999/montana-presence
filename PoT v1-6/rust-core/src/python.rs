//! Python bindings using PyO3
//!
//! Exposes Rust crypto primitives to Python for use with existing node.

#[cfg(feature = "python")]
use pyo3::prelude::*;

#[cfg(feature = "python")]
pub fn register_module(m: &PyModule) -> PyResult<()> {
    // VDF functions
    m.add_function(wrap_pyfunction!(py_vdf_compute, m)?)?;
    m.add_function(wrap_pyfunction!(py_vdf_verify, m)?)?;

    // VRF functions
    m.add_function(wrap_pyfunction!(py_vrf_prove, m)?)?;
    m.add_function(wrap_pyfunction!(py_vrf_verify, m)?)?;

    // Signature functions
    m.add_function(wrap_pyfunction!(py_sign, m)?)?;
    m.add_function(wrap_pyfunction!(py_verify, m)?)?;

    // Hash functions
    m.add_function(wrap_pyfunction!(py_sha256, m)?)?;
    m.add_function(wrap_pyfunction!(py_blake2b_256, m)?)?;

    // Ring signatures
    m.add_function(wrap_pyfunction!(py_lsag_sign, m)?)?;
    m.add_function(wrap_pyfunction!(py_lsag_verify, m)?)?;

    // Stealth addresses
    m.add_function(wrap_pyfunction!(py_generate_one_time_key, m)?)?;
    m.add_function(wrap_pyfunction!(py_check_output_ownership, m)?)?;

    // Pedersen commitments
    m.add_function(wrap_pyfunction!(py_pedersen_commit, m)?)?;
    m.add_function(wrap_pyfunction!(py_pedersen_verify, m)?)?;

    Ok(())
}

// ============================================================================
// VDF Bindings
// ============================================================================

#[cfg(feature = "python")]
#[pyfunction]
fn py_vdf_compute(input: Vec<u8>, iterations: u64) -> PyResult<(Vec<u8>, Vec<u8>)> {
    use crate::crypto::vdf::VDF;

    let vdf = VDF::new(iterations);
    let proof = vdf.compute(&input)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    Ok((proof.output, proof.proof))
}

#[cfg(feature = "python")]
#[pyfunction]
fn py_vdf_verify(input: Vec<u8>, output: Vec<u8>, proof: Vec<u8>, iterations: u64) -> PyResult<bool> {
    use crate::crypto::vdf::{VDF, VDFProof};

    let vdf = VDF::new(iterations);
    let vdf_proof = VDFProof {
        input: input.clone(),
        output,
        proof,
        iterations,
    };

    vdf.verify(&vdf_proof)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

// ============================================================================
// VRF Bindings
// ============================================================================

#[cfg(feature = "python")]
#[pyfunction]
fn py_vrf_prove(secret_key: [u8; 32], input: Vec<u8>) -> PyResult<(Vec<u8>, Vec<u8>)> {
    use crate::crypto::vrf::VRF;

    let vrf = VRF::from_secret_key(&secret_key)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    let (output, proof) = vrf.prove(&input)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    Ok((output.0.to_vec(), proof.to_bytes().to_vec()))
}

#[cfg(feature = "python")]
#[pyfunction]
fn py_vrf_verify(public_key: [u8; 32], input: Vec<u8>, proof: [u8; 96]) -> PyResult<Vec<u8>> {
    use crate::crypto::vrf::{VRF, VRFProof};

    let vrf_proof = VRFProof::from_bytes(&proof);
    let output = VRF::verify(&public_key, &input, &vrf_proof)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    Ok(output.0.to_vec())
}

// ============================================================================
// Signature Bindings
// ============================================================================

#[cfg(feature = "python")]
#[pyfunction]
fn py_sign(secret_key: [u8; 32], message: Vec<u8>) -> PyResult<Vec<u8>> {
    use crate::crypto::signatures::{SecretKey, sign};

    let sk = SecretKey::from_bytes(&secret_key);
    let sig = sign(&sk, &message);
    Ok(sig.0.to_vec())
}

#[cfg(feature = "python")]
#[pyfunction]
fn py_verify(public_key: [u8; 32], message: Vec<u8>, signature: [u8; 64]) -> PyResult<bool> {
    use crate::crypto::signatures::{PublicKey, Signature, verify};

    let pk = PublicKey::from_bytes(&public_key);
    let sig = Signature::from_bytes(&signature);

    match verify(&pk, &message, &sig) {
        Ok(()) => Ok(true),
        Err(_) => Ok(false),
    }
}

// ============================================================================
// Hash Bindings
// ============================================================================

#[cfg(feature = "python")]
#[pyfunction]
fn py_sha256(data: Vec<u8>) -> Vec<u8> {
    crate::crypto::hash::sha256(&data).to_vec()
}

#[cfg(feature = "python")]
#[pyfunction]
fn py_blake2b_256(data: Vec<u8>) -> Vec<u8> {
    crate::crypto::hash::blake2b_256(&data).to_vec()
}

// ============================================================================
// Ring Signature Bindings
// ============================================================================

#[cfg(feature = "python")]
#[pyfunction]
fn py_lsag_sign(
    message: Vec<u8>,
    ring: Vec<[u8; 32]>,
    secret_key: [u8; 32],
    secret_index: usize,
) -> PyResult<(Vec<u8>, Vec<u8>)> {
    use crate::privacy::ring::LSAG;
    use rand::rngs::OsRng;

    let sig = LSAG::sign(&message, &ring, &secret_key, secret_index, &mut OsRng)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    Ok((sig.key_image.0.to_vec(), sig.to_bytes()))
}

#[cfg(feature = "python")]
#[pyfunction]
fn py_lsag_verify(
    message: Vec<u8>,
    ring: Vec<[u8; 32]>,
    signature: Vec<u8>,
    ring_size: usize,
) -> PyResult<bool> {
    use crate::privacy::ring::{LSAG, RingSignature};

    let sig = RingSignature::from_bytes(&signature, ring_size)
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("Invalid signature format"))?;

    LSAG::verify(&message, &ring, &sig)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

// ============================================================================
// Stealth Address Bindings
// ============================================================================

#[cfg(feature = "python")]
#[pyfunction]
fn py_generate_one_time_key(
    view_public: [u8; 32],
    spend_public: [u8; 32],
    output_index: u64,
) -> PyResult<(Vec<u8>, Vec<u8>)> {
    use crate::privacy::stealth::{StealthAddress, OneTimeKey};
    use rand::rngs::OsRng;

    let addr = StealthAddress::new(view_public, spend_public);
    let otk = OneTimeKey::generate(&addr, output_index, &mut OsRng)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    Ok((otk.ephemeral.to_vec(), otk.public_key.to_vec()))
}

#[cfg(feature = "python")]
#[pyfunction]
fn py_check_output_ownership(
    ephemeral: [u8; 32],
    public_key: [u8; 32],
    output_index: u64,
    view_secret: [u8; 32],
    spend_public: [u8; 32],
) -> PyResult<bool> {
    use crate::privacy::stealth::OneTimeKey;

    OneTimeKey::check_ownership(&ephemeral, &public_key, output_index, &view_secret, &spend_public)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

// ============================================================================
// Pedersen Commitment Bindings
// ============================================================================

#[cfg(feature = "python")]
#[pyfunction]
fn py_pedersen_commit(value: u64) -> PyResult<(Vec<u8>, Vec<u8>)> {
    use crate::privacy::pedersen::PedersenCommitment;
    use rand::rngs::OsRng;

    let (commitment, blinding) = PedersenCommitment::commit(value, &mut OsRng);
    Ok((commitment.0.to_vec(), blinding.to_bytes().to_vec()))
}

#[cfg(feature = "python")]
#[pyfunction]
fn py_pedersen_verify(commitment: [u8; 32], value: u64, blinding: [u8; 32]) -> bool {
    use crate::privacy::pedersen::PedersenCommitment;
    use curve25519_dalek::scalar::Scalar;

    let c = PedersenCommitment::from_bytes(commitment);
    let b = Scalar::from_bytes_mod_order(blinding);
    c.verify(value, &b)
}
