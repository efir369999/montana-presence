//
//  MontanaContractsApp.swift
//  Montana Contracts — Bitcoin Pizza Style
//
//  App 3 of 3: Contracts + Voting + Escrow
//  Bundle ID: network.montana.contracts
//

import SwiftUI
import MontanaCore

@main
struct MontanaContractsApp: App {
    init() {
        Montana.initialize()
    }

    var body: some Scene {
        WindowGroup {
            ContractsMainView()
                .preferredColorScheme(.dark)
        }
    }
}

struct ContractsMainView: View {
    @State private var contracts: [ContractItem] = []
    @State private var showNewContract = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if contracts.isEmpty {
                    EmptyContractsView()
                } else {
                    ScrollView {
                        LazyVStack(spacing: 12) {
                            ForEach(contracts) { contract in
                                ContractCardView(contract: contract)
                            }
                        }
                        .padding()
                    }
                }
            }
            .background(MontanaTheme.background)
            .navigationTitle("Контракты")
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button {
                        MontanaLinks.openWallet()
                    } label: {
                        Image(systemName: "creditcard")
                    }
                    .foregroundColor(MontanaTheme.primary)
                }

                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        showNewContract = true
                    } label: {
                        Image(systemName: "plus.circle.fill")
                    }
                    .foregroundColor(MontanaTheme.primary)
                }
            }
            .sheet(isPresented: $showNewContract) {
                NewContractView()
            }
        }
    }
}

struct EmptyContractsView: View {
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "doc.text")
                .font(.system(size: 60))
                .foregroundColor(.secondary)

            Text("Контрактов пока нет")
                .font(.headline)

            Text("Создай контракт через Юнону — она проведёт тебя через процесс")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)

            Button {
                MontanaLinks.openJunona(message: "Хочу создать контракт")
            } label: {
                HStack {
                    Image(systemName: "bubble.left.fill")
                    Text("Открыть Юнону")
                }
                .padding()
                .background(MontanaTheme.primary)
                .cornerRadius(12)
                .foregroundColor(.white)
            }
        }
    }
}

struct ContractItem: Identifiable {
    let id: String
    let amount: Double
    let description: String
    let status: Status
    let votes: Int
    let requiredVotes: Int

    enum Status: String {
        case draft = "DRAFT"
        case voting = "VOTING"
        case pending = "PENDING"
        case accepted = "ACCEPTED"
        case completed = "COMPLETED"
        case rejected = "REJECTED"

        var color: Color {
            switch self {
            case .draft: return .secondary
            case .voting: return MontanaTheme.warning
            case .pending: return MontanaTheme.primary
            case .accepted, .completed: return MontanaTheme.success
            case .rejected: return MontanaTheme.error
            }
        }

        var displayName: String {
            switch self {
            case .draft: return "Черновик"
            case .voting: return "Голосование"
            case .pending: return "Ожидание"
            case .accepted: return "Принят"
            case .completed: return "Завершён"
            case .rejected: return "Отклонён"
            }
        }
    }
}

struct ContractCardView: View {
    let contract: ContractItem

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(contract.status.displayName)
                    .font(.caption)
                    .fontWeight(.medium)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(contract.status.color)
                    .cornerRadius(8)

                Spacer()

                Text("#\(contract.id)")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            HStack(alignment: .lastTextBaseline) {
                Text("\(Int(contract.amount))")
                    .font(.system(size: 32, weight: .bold, design: .rounded))
                Text("Ɉ")
                    .font(.title3)
                    .foregroundColor(MontanaTheme.primary)
            }

            Text(contract.description)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .lineLimit(2)

            if contract.status == .voting {
                VotingProgressView(current: contract.votes, required: contract.requiredVotes)
            }
        }
        .padding()
        .background(MontanaTheme.cardBackground)
        .cornerRadius(16)
    }
}

struct VotingProgressView: View {
    let current: Int
    let required: Int

    var progress: Double {
        guard required > 0 else { return 0 }
        return Double(current) / Double(required)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("Голосование")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Spacer()
                Text("\(current)/\(required)")
                    .font(.caption)
                    .fontWeight(.medium)
            }

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.secondary.opacity(0.3))
                    RoundedRectangle(cornerRadius: 4)
                        .fill(MontanaTheme.warning)
                        .frame(width: geo.size.width * progress)
                }
            }
            .frame(height: 8)
        }
    }
}

struct NewContractView: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                Image(systemName: "doc.badge.plus")
                    .font(.system(size: 60))
                    .foregroundColor(MontanaTheme.primary)

                Text("Создание контракта")
                    .font(.title2)
                    .fontWeight(.bold)

                Text("Контракты создаются через Юнону. Она проверит условия и выступит арбитром.")
                    .multilineTextAlignment(.center)
                    .foregroundColor(.secondary)
                    .padding(.horizontal)

                Button {
                    MontanaLinks.openJunona(message: "Хочу создать контракт")
                    dismiss()
                } label: {
                    HStack {
                        Image(systemName: "bubble.left.fill")
                        Text("Перейти к Юноне")
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(MontanaTheme.primary)
                    .cornerRadius(12)
                    .foregroundColor(.white)
                }
                .padding(.horizontal)

                Spacer()
            }
            .padding(.top, 40)
            .background(MontanaTheme.background)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Закрыть") { dismiss() }
                }
            }
        }
    }
}
