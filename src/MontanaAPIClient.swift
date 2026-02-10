import Foundation

class MontanaAPIClient {
    private let endpoints: [(name: String, url: String)] = [
        ("efir.org", "https://efir.org"),
        ("Amsterdam", "http://72.56.102.240"),
        ("Almaty", "http://91.200.148.93")
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
