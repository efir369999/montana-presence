import Foundation

class MontanaAPIClient {
    private let endpoints: [(name: String, url: String)] = [
        ("Primary", "https://efir.org"),
        ("Amsterdam", "http://72.56.102.240:5000"),
        ("Moscow", "http://176.124.208.93:8889"),
        ("Almaty", "http://91.200.148.93:5000")
    ]

    func reportPresence(address: String, seconds: Int) async throws -> Int {
        return try await tryAllEndpoints { endpoint in
            guard let url = URL(string: "\(endpoint)/api/presence") else {
                throw URLError(.badURL)
            }
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue(address, forHTTPHeaderField: "X-Device-ID")
            request.timeoutInterval = 10
            request.httpBody = try JSONSerialization.data(withJSONObject: ["seconds": seconds])

            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let balance = json["balance"] as? Int else {
                throw URLError(.cannotParseResponse)
            }
            return balance
        }
    }

    func fetchBalance(address: String) async throws -> Int {
        return try await tryAllEndpoints { endpoint in
            let encoded = address.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? address
            guard let url = URL(string: "\(endpoint)/api/balance/\(encoded)") else {
                throw URLError(.badURL)
            }
            var request = URLRequest(url: url)
            request.timeoutInterval = 10

            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let balance = json["balance"] as? Int else {
                throw URLError(.cannotParseResponse)
            }
            return balance
        }
    }

    func lookupWallet(identifier: String) async throws -> (address: String, alias: String) {
        return try await tryAllEndpoints { endpoint in
            let encoded = identifier.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? identifier
            guard let url = URL(string: "\(endpoint)/api/wallet/lookup/\(encoded)") else {
                throw URLError(.badURL)
            }
            var request = URLRequest(url: url)
            request.timeoutInterval = 10

            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                throw URLError(.cannotParseResponse)
            }

            // Extract mt address from crypto_hash
            let cryptoHash = json["crypto_hash"] as? String ?? ""
            let mtAddress = "mt" + cryptoHash
            let alias = json["alias"] as? String ?? ""
            return (mtAddress, alias)
        }
    }

    func transfer(from: String, to: String, amount: Int) async throws {
        try await tryAllEndpoints { endpoint in
            guard let url = URL(string: "\(endpoint)/api/transfer") else {
                throw URLError(.badURL)
            }
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.timeoutInterval = 15

            let timestamp = ISO8601DateFormatter().string(from: Date())
            let body: [String: Any] = [
                "from_address": from,
                "to_address": to,
                "amount": amount,
                "timestamp": timestamp
            ]
            request.httpBody = try JSONSerialization.data(withJSONObject: body)

            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                throw URLError(.cannotParseResponse)
            }

            if httpResponse.statusCode != 200 {
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let error = json["error"] as? String {
                    throw NSError(domain: "Montana", code: httpResponse.statusCode,
                                  userInfo: [NSLocalizedDescriptionKey: error])
                }
                throw URLError(.cannotParseResponse)
            }
            return ()
        }
    }

    struct NetworkStatus {
        var nodes: [(name: String, location: String, online: Bool)] = []
        var onlineCount: Int = 0
        var totalNodes: Int = 0
        var health: String = "0%"
    }

    struct ProtocolStatus {
        var version: String = ""
        var mode: String = ""
        var crypto: String = ""
    }

    struct LedgerVerification {
        var ledgerBalance: Int = 0
        var cachedBalance: Int = 0
        var verified: Bool = false
    }

    func fetchStatus() async throws -> (network: NetworkStatus, protocol_: ProtocolStatus) {
        return try await tryAllEndpoints { endpoint in
            guard let url = URL(string: "\(endpoint)/api/status") else {
                throw URLError(.badURL)
            }
            var request = URLRequest(url: url)
            request.timeoutInterval = 10

            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                throw URLError(.cannotParseResponse)
            }

            var net = NetworkStatus()
            if let network = json["network"] as? [String: Any],
               let nodes = network["nodes"] as? [String: [String: Any]],
               let summary = network["summary"] as? [String: Any] {
                net.onlineCount = summary["online_nodes"] as? Int ?? 0
                net.totalNodes = summary["total_nodes"] as? Int ?? 0
                net.health = summary["network_health"] as? String ?? "0%"
                for (_, info) in nodes {
                    net.nodes.append((
                        name: info["name"] as? String ?? "",
                        location: info["location"] as? String ?? "",
                        online: info["online"] as? Bool ?? false
                    ))
                }
                net.nodes.sort { $0.name < $1.name }
            }

            var proto = ProtocolStatus()
            if let montana = json["montana"] as? [String: Any] {
                proto.version = montana["version"] as? String ?? ""
                proto.mode = montana["mode"] as? String ?? ""
                proto.crypto = montana["crypto"] as? String ?? ""
            }

            return (net, proto)
        }
    }

    func fetchLedgerVerify(address: String) async throws -> LedgerVerification {
        return try await tryAllEndpoints { endpoint in
            let encoded = address.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? address
            guard let url = URL(string: "\(endpoint)/api/ledger/verify/\(encoded)") else {
                throw URLError(.badURL)
            }
            var request = URLRequest(url: url)
            request.timeoutInterval = 10

            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                throw URLError(.cannotParseResponse)
            }

            return LedgerVerification(
                ledgerBalance: json["ledger_balance"] as? Int ?? 0,
                cachedBalance: json["cached_balance"] as? Int ?? 0,
                verified: json["verified"] as? Bool ?? false
            )
        }
    }

    private func tryAllEndpoints<T>(_ operation: (String) async throws -> T) async throws -> T {
        var lastError: Error = URLError(.cannotConnectToHost)
        for endpoint in endpoints {
            do {
                return try await operation(endpoint.url)
            } catch {
                lastError = error
                continue
            }
        }
        throw lastError
    }
}
