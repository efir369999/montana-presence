import Foundation

class API {
    static let shared = API()
    private let baseURL = "http://72.56.102.240"

    private init() {}

    // MARK: - User
    func getUser(deviceId: String, completion: @escaping (Result<User, Error>) -> Void) {
        var request = URLRequest(url: URL(string: "\(baseURL)/api/user")!)
        request.addValue(deviceId, forHTTPHeaderField: "X-Device-ID")

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            guard let data = data else {
                completion(.failure(APIError.noData))
                return
            }
            do {
                let user = try JSONDecoder().decode(User.self, from: data)
                completion(.success(user))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }

    // MARK: - Login
    func checkLoginStatus(sessionId: String, completion: @escaping (Result<LoginSession, Error>) -> Void) {
        let url = URL(string: "\(baseURL)/api/login-status?session=\(sessionId)")!

        URLSession.shared.dataTask(with: url) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            guard let data = data else {
                completion(.failure(APIError.noData))
                return
            }
            do {
                let session = try JSONDecoder().decode(LoginSession.self, from: data)
                completion(.success(session))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }

    // MARK: - Presence
    func syncPresence(deviceId: String, seconds: Int) {
        var request = URLRequest(url: URL(string: "\(baseURL)/api/presence")!)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue(deviceId, forHTTPHeaderField: "X-Device-ID")
        request.httpBody = try? JSONEncoder().encode(["seconds": seconds])

        URLSession.shared.dataTask(with: request).resume()
    }

    // MARK: - Contacts
    func getContacts(deviceId: String, completion: @escaping (Result<[Contact], Error>) -> Void) {
        var request = URLRequest(url: URL(string: "\(baseURL)/api/contacts")!)
        request.addValue(deviceId, forHTTPHeaderField: "X-Device-ID")

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            guard let data = data else {
                completion(.failure(APIError.noData))
                return
            }
            do {
                struct Response: Codable { let contacts: [Contact] }
                let response = try JSONDecoder().decode(Response.self, from: data)
                completion(.success(response.contacts))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }

    func saveContact(telegramId: String, name: String, phone: String, completion: @escaping (Bool) -> Void) {
        var request = URLRequest(url: URL(string: "\(baseURL)/api/contacts")!)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: String] = [
            "telegram_id": telegramId,
            "name": name,
            "phone": phone
        ]
        request.httpBody = try? JSONEncoder().encode(body)

        URLSession.shared.dataTask(with: request) { data, _, error in
            completion(error == nil)
        }.resume()
    }

    // MARK: - Transfer
    func transfer(deviceId: String, to: String, amount: Int, completion: @escaping (Result<TransferResponse, Error>) -> Void) {
        var request = URLRequest(url: URL(string: "\(baseURL)/api/transfer")!)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue(deviceId, forHTTPHeaderField: "X-Device-ID")
        request.httpBody = try? JSONEncoder().encode(TransferRequest(to: to, amount: amount))

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            guard let data = data else {
                completion(.failure(APIError.noData))
                return
            }
            do {
                let response = try JSONDecoder().decode(TransferResponse.self, from: data)
                completion(.success(response))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }

    // MARK: - Chat
    func sendMessage(deviceId: String, message: String, completion: @escaping (Result<String, Error>) -> Void) {
        var request = URLRequest(url: URL(string: "\(baseURL)/api/chat")!)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue(deviceId, forHTTPHeaderField: "X-Device-ID")
        request.httpBody = try? JSONEncoder().encode(["message": message])

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            guard let data = data else {
                completion(.failure(APIError.noData))
                return
            }
            do {
                struct Response: Codable { let response: String }
                let response = try JSONDecoder().decode(Response.self, from: data)
                completion(.success(response.response))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }
}

// MARK: - P2P Messages
    func sendP2PMessage(deviceId: String, toPhone: String, content: String, completion: @escaping (Result<P2PMessage, Error>) -> Void) {
        var request = URLRequest(url: URL(string: "\(baseURL)/api/messages")!)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue(deviceId, forHTTPHeaderField: "X-Device-ID")

        let body: [String: String] = [
            "to_phone": toPhone,
            "content": content
        ]
        request.httpBody = try? JSONEncoder().encode(body)

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            guard let data = data else {
                completion(.failure(APIError.noData))
                return
            }
            do {
                let message = try JSONDecoder().decode(P2PMessage.self, from: data)
                completion(.success(message))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }

    func getMessages(deviceId: String, withPhone: String, completion: @escaping (Result<[P2PMessage], Error>) -> Void) {
        var components = URLComponents(string: "\(baseURL)/api/messages")!
        components.queryItems = [URLQueryItem(name: "with", value: withPhone)]

        var request = URLRequest(url: components.url!)
        request.addValue(deviceId, forHTTPHeaderField: "X-Device-ID")

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            guard let data = data else {
                completion(.failure(APIError.noData))
                return
            }
            do {
                struct Response: Codable { let messages: [P2PMessage] }
                let response = try JSONDecoder().decode(Response.self, from: data)
                completion(.success(response.messages))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }

    func getConversations(deviceId: String, completion: @escaping (Result<[Conversation], Error>) -> Void) {
        var request = URLRequest(url: URL(string: "\(baseURL)/api/conversations")!)
        request.addValue(deviceId, forHTTPHeaderField: "X-Device-ID")

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            guard let data = data else {
                completion(.failure(APIError.noData))
                return
            }
            do {
                struct ConvResponse: Codable {
                    let contactPhone: String
                    let contactName: String
                    let lastMessage: String
                    let lastMessageTime: String
                    let unreadCount: Int

                    enum CodingKeys: String, CodingKey {
                        case contactPhone = "contact_phone"
                        case contactName = "contact_name"
                        case lastMessage = "last_message"
                        case lastMessageTime = "last_message_time"
                        case unreadCount = "unread_count"
                    }
                }
                struct Response: Codable { let conversations: [ConvResponse] }
                let response = try JSONDecoder().decode(Response.self, from: data)

                let dateFormatter = ISO8601DateFormatter()
                let conversations = response.conversations.map { conv in
                    Conversation(
                        contactPhone: conv.contactPhone,
                        contactName: conv.contactName,
                        lastMessage: conv.lastMessage,
                        lastMessageTime: dateFormatter.date(from: conv.lastMessageTime) ?? Date(),
                        unreadCount: conv.unreadCount
                    )
                }
                completion(.success(conversations))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }
}

enum APIError: Error {
    case noData
    case invalidResponse
}
