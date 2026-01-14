//! Montana ACP Node
//!
//! ФАЗА 1: Минимальный stub для тестирования сети
//! ФАЗА 2: Полная интеграция с ConsensusEngine

use clap::Parser;
use montana::{Network, NetConfig, NodeType, NODE_FULL, NODE_PRESENCE};
use std::path::PathBuf;
use tracing::{info, error};

#[derive(Parser)]
#[command(name = "montana", version, about = "Montana ACP Node")]
struct Args {
    /// Node type: full, light, client
    #[arg(short, long, default_value = "full")]
    node_type: String,

    /// Listen port
    #[arg(short, long, default_value = "19333")]
    port: u16,

    /// Data directory
    #[arg(short, long, default_value = "./data")]
    data_dir: PathBuf,
}

#[tokio::main]
async fn main() {
    // Initialize logging
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("montana=info".parse().unwrap()),
        )
        .init();

    let args = Args::parse();

    let node_type = match args.node_type.as_str() {
        "full" => NodeType::Full,
        "light" => NodeType::Light,
        "client" => NodeType::Client,
        _ => {
            error!("Invalid node type. Use: full, light, client");
            return;
        }
    };

    info!("Starting Montana Node ({:?})", node_type);

    let net_config = NetConfig {
        listen_port: args.port,
        data_dir: args.data_dir.clone(),
        node_type,
        services: NODE_FULL | NODE_PRESENCE,
        ..Default::default()
    };

    // Initialize network
    let (network, mut _event_rx) = match Network::new(net_config).await {
        Ok(res) => res,
        Err(e) => {
            error!("Failed to initialize network: {}", e);
            return;
        }
    };

    // Start network
    if let Err(e) = network.start().await {
        error!("Failed to start network: {}", e);
        return;
    }

    info!("Network started on port {}", args.port);
    info!("Node running (Phase 1 stub - no consensus engine yet)");
    info!("Press Ctrl+C to stop.");

    // Wait for shutdown signal
    if let Err(e) = tokio::signal::ctrl_c().await {
        error!("Failed to listen for Ctrl+C: {}", e);
    }

    info!("Shutting down...");
}
