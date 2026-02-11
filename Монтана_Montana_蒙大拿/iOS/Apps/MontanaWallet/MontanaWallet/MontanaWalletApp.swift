//
//  MontanaWalletApp.swift
//  Montana Wallet — Кошелёк Ɉ
//
//  App 1 of 3: Wallet + Balance + Transfers
//  Bundle ID: network.montana.wallet
//

import SwiftUI
import MontanaCore

@main
struct MontanaWalletApp: App {
    init() {
        Montana.initialize()
    }

    var body: some Scene {
        WindowGroup {
            WalletMainView()
                .preferredColorScheme(.dark)
        }
    }
}

struct WalletMainView: View {
    @State private var balance: Double = 0
    @State private var address: String = ""

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // Balance
                VStack(spacing: 8) {
                    Text("Баланс")
                        .foregroundColor(.secondary)

                    HStack(alignment: .lastTextBaseline) {
                        Text("\(Int(balance))")
                            .font(.system(size: 56, weight: .bold, design: .rounded))

                        Text("Ɉ")
                            .font(.title)
                            .foregroundColor(MontanaTheme.primary)
                    }
                }
                .padding(.top, 40)

                // Actions
                HStack(spacing: 20) {
                    ActionButton(title: "Отправить", icon: "arrow.up.circle.fill") {
                        // Transfer
                    }

                    ActionButton(title: "Получить", icon: "arrow.down.circle.fill") {
                        // Receive
                    }

                    ActionButton(title: "Юнона", icon: "bubble.left.fill") {
                        MontanaLinks.openJunona()
                    }
                }
                .padding()

                // Address
                if !address.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Адрес")
                            .font(.caption)
                            .foregroundColor(.secondary)

                        Text(address)
                            .font(.system(.footnote, design: .monospaced))
                    }
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(MontanaTheme.cardBackground)
                    .cornerRadius(12)
                    .padding(.horizontal)
                }

                Spacer()

                // Cross-app navigation
                HStack {
                    if MontanaLinks.isInstalled(MontanaLinks.contractsScheme) {
                        Button("Контракты") {
                            MontanaLinks.openContracts()
                        }
                        .foregroundColor(MontanaTheme.primary)
                    }
                }
                .padding()
            }
            .background(MontanaTheme.background)
            .navigationTitle("Кошелёк")
            .onAppear {
                loadWallet()
            }
        }
    }

    private func loadWallet() {
        address = MontanaKeychain.shared.walletAddress ?? ""
        // Load balance from API
    }
}

struct ActionButton: View {
    let title: String
    let icon: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.title2)
                Text(title)
                    .font(.caption)
            }
            .frame(width: 80, height: 70)
            .background(MontanaTheme.cardBackground)
            .cornerRadius(12)
        }
        .foregroundColor(.white)
    }
}
