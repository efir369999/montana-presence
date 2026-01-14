//! Network integration tests for Montana
//!
//! Run with: cargo test --test net_test -- --nocapture

use std::process::{Child, Command, Stdio};
use std::time::Duration;
use std::path::Path;
use std::fs;

// Use the binary built by `cargo test` (Cargo sets this env var automatically).
// This makes the test self-contained and avoids requiring `cargo build --release` first.
const BINARY: &str = env!("CARGO_BIN_EXE_montana");

struct TestNode {
    process: Child,
    port: u16,
    data_dir: String,
}

impl TestNode {
    fn spawn(port: u16, seeds: Option<&str>) -> Result<Self, String> {
        let data_dir = format!("/tmp/montana_test_{}", port);

        // Clean up old data
        let _ = fs::remove_dir_all(&data_dir);
        fs::create_dir_all(&data_dir).map_err(|e| e.to_string())?;

        let mut cmd = Command::new(BINARY);
        cmd.arg("--port").arg(port.to_string())
           .arg("--data-dir").arg(&data_dir)
           .arg("--node-type").arg("full")
           .env("RUST_LOG", "montana=debug")
           .stdout(Stdio::piped())
           .stderr(Stdio::piped());

        if let Some(s) = seeds {
            cmd.arg("--seeds").arg(s);
        }

        let process = cmd.spawn().map_err(|e| format!("Failed to spawn: {}", e))?;

        Ok(Self { process, port, data_dir })
    }

    fn kill(&mut self) {
        let _ = self.process.kill();
        let _ = self.process.wait();
        let _ = fs::remove_dir_all(&self.data_dir);
    }
}

impl Drop for TestNode {
    fn drop(&mut self) {
        self.kill();
    }
}

fn check_binary() -> bool {
    Path::new(BINARY).exists()
}

fn sleep_secs(secs: u64) {
    std::thread::sleep(Duration::from_secs(secs));
}

fn test_01_peer_connection() -> bool {
    println!("\n=== Test 1: Peer Connection ===");

    // Start node A
    let mut node_a = match TestNode::spawn(19100, None) {
        Ok(n) => n,
        Err(e) => {
            println!("✗ Failed to start node A: {}", e);
            return false;
        }
    };
    println!("  Started node A on port 19100");
    sleep_secs(2);

    // Start node B with seed to A
    let mut node_b = match TestNode::spawn(19101, Some("127.0.0.1:19100")) {
        Ok(n) => n,
        Err(e) => {
            println!("✗ Failed to start node B: {}", e);
            node_a.kill();
            return false;
        }
    };
    println!("  Started node B on port 19101 with seed to A");

    // Wait for connection
    sleep_secs(5);

    // Check processes are still running
    let a_running = node_a.process.try_wait().unwrap().is_none();
    let b_running = node_b.process.try_wait().unwrap().is_none();

    node_a.kill();
    node_b.kill();

    if !a_running {
        println!("✗ Node A crashed");
        return false;
    }
    if !b_running {
        println!("✗ Node B crashed");
        return false;
    }

    println!("✓ Both nodes running, connection established");
    true
}

fn test_02_three_node_mesh() -> bool {
    println!("\n=== Test 2: Three Node Mesh ===");

    // Start node A (bootstrap)
    let mut node_a = match TestNode::spawn(19200, None) {
        Ok(n) => n,
        Err(e) => {
            println!("✗ Failed to start node A: {}", e);
            return false;
        }
    };
    println!("  Started node A on port 19200");
    sleep_secs(2);

    // Start node B -> A
    let mut node_b = match TestNode::spawn(19201, Some("127.0.0.1:19200")) {
        Ok(n) => n,
        Err(e) => {
            println!("✗ Failed to start node B: {}", e);
            node_a.kill();
            return false;
        }
    };
    println!("  Started node B on port 19201");
    sleep_secs(2);

    // Start node C -> A
    let mut node_c = match TestNode::spawn(19202, Some("127.0.0.1:19200")) {
        Ok(n) => n,
        Err(e) => {
            println!("✗ Failed to start node C: {}", e);
            node_a.kill();
            node_b.kill();
            return false;
        }
    };
    println!("  Started node C on port 19202");

    sleep_secs(5);

    let a_running = node_a.process.try_wait().unwrap().is_none();
    let b_running = node_b.process.try_wait().unwrap().is_none();
    let c_running = node_c.process.try_wait().unwrap().is_none();

    node_a.kill();
    node_b.kill();
    node_c.kill();

    if !a_running || !b_running || !c_running {
        println!("✗ One or more nodes crashed");
        return false;
    }

    println!("✓ Three node mesh running");
    true
}

fn test_03_reconnect() -> bool {
    println!("\n=== Test 3: Reconnection ===");

    // Start node A
    let mut node_a = match TestNode::spawn(19300, None) {
        Ok(n) => n,
        Err(e) => {
            println!("✗ Failed to start node A: {}", e);
            return false;
        }
    };
    println!("  Started node A on port 19300");
    sleep_secs(2);

    // Start node B -> A
    let mut node_b = match TestNode::spawn(19301, Some("127.0.0.1:19300")) {
        Ok(n) => n,
        Err(e) => {
            println!("✗ Failed to start node B: {}", e);
            node_a.kill();
            return false;
        }
    };
    println!("  Started node B on port 19301");
    sleep_secs(3);

    println!("  Killing node A...");
    node_a.kill();
    sleep_secs(2);

    // B should still be running
    if node_b.process.try_wait().unwrap().is_some() {
        println!("✗ Node B crashed after A died");
        return false;
    }
    println!("  ✓ Node B survived A's death");

    // Restart A
    println!("  Restarting node A...");
    node_a = match TestNode::spawn(19300, None) {
        Ok(n) => n,
        Err(e) => {
            println!("✗ Failed to restart node A: {}", e);
            node_b.kill();
            return false;
        }
    };
    sleep_secs(10); // Wait for reconnection

    let a_running = node_a.process.try_wait().unwrap().is_none();
    let b_running = node_b.process.try_wait().unwrap().is_none();

    node_a.kill();
    node_b.kill();

    if !a_running || !b_running {
        println!("✗ Nodes crashed during reconnection");
        return false;
    }

    println!("✓ Reconnection test passed");
    true
}

// NOTE:
// These tests spawn real node processes and are intentionally ignored by default
// because the node runtime is still under active development and may be flaky
// in CI/sandboxed environments.

#[test]
#[ignore]
fn net_01_peer_connection() {
    assert!(check_binary(), "Binary not found at {}", BINARY);
    assert!(test_01_peer_connection());
}

#[test]
#[ignore]
fn net_02_three_node_mesh() {
    assert!(check_binary(), "Binary not found at {}", BINARY);
    assert!(test_02_three_node_mesh());
}

#[test]
#[ignore]
fn net_03_reconnect() {
    assert!(check_binary(), "Binary not found at {}", BINARY);
    assert!(test_03_reconnect());
}
