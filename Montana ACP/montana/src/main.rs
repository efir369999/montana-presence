//! Montana ACP Node
//!
//! ФАЗА 2: Event-driven architecture with ConsensusEngine

use clap::Parser;
use montana::{
    ConsensusEngine, EngineConfig, Network, NetConfig, NetEvent,
    NodeType, NODE_FULL, NODE_PRESENCE,
};
use std::path::PathBuf;
use tracing::{info, warn, error, debug};

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
    let (network, mut event_rx) = match Network::new(net_config).await {
        Ok(res) => res,
        Err(e) => {
            error!("Failed to initialize network: {}", e);
            return;
        }
    };

    // Initialize consensus engine
    let engine_config = EngineConfig {
        node_type,
        genesis_hash: [0u8; 32], // TODO: Load from config
    };
    let engine = ConsensusEngine::new(engine_config);

    // Start network
    if let Err(e) = network.start().await {
        error!("Failed to start network: {}", e);
        return;
    }

    info!("Network started on port {}", args.port);
    info!("Consensus engine initialized");
    info!("Press Ctrl+C to stop.");

    // Event loop: Network → Engine
    let network_ref = &network;
    let engine_ref = &engine;

    tokio::select! {
        _ = async {
            while let Some(event) = event_rx.recv().await {
                match &event {
                    NetEvent::Tau1Tick { tau1_index, .. } => {
                        debug!("τ₁ tick: {}", tau1_index);
                    }
                    NetEvent::Tau2Ended { tau2_index, .. } => {
                        info!("τ₂ ended: {}", tau2_index);
                    }
                    NetEvent::PeerConnected(addr) => {
                        debug!("Peer connected: {}", addr);
                    }
                    NetEvent::PeerDisconnected(addr) => {
                        debug!("Peer disconnected: {}", addr);
                    }
                    _ => {}
                }

                match engine_ref.handle_event(event, network_ref).await {
                    Ok(Some(action)) => {
                        debug!("Engine action: {:?}", action);
                    }
                    Ok(None) => {}
                    Err(e) => {
                        warn!("Engine error: {:?}", e);
                    }
                }
            }
        } => {}
        _ = tokio::signal::ctrl_c() => {
            info!("Received Ctrl+C, shutting down...");
        }
    }

    info!("Shutting down...");
}
