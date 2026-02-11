import Foundation

// MARK: - User
struct User: Codable, Identifiable {
    let id: String?
    let phone: String
    let name: String?
    let balance: Int
    let telegramId: String?

    enum CodingKeys: String, CodingKey {
        case id = "device_id"
        case phone
        case name
        case balance
        case telegramId = "telegram_id"
    }
}

// MARK: - Contact
struct Contact: Codable, Identifiable {
    var id: String { phone }
    let name: String
    let phone: String
}

// MARK: - Login Session
struct LoginSession: Codable {
    let sessionId: String
    let deviceId: String?
    let pending: Bool?

    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case deviceId = "device_id"
        case pending
    }
}

// MARK: - Transfer
struct TransferRequest: Codable {
    let to: String
    let amount: Int
}

struct TransferResponse: Codable {
    let success: Bool
    let newBalance: Int?
    let error: String?

    enum CodingKeys: String, CodingKey {
        case success
        case newBalance = "new_balance"
        case error
    }
}

// MARK: - Chat Message
struct ChatMessage: Identifiable, Codable {
    let id: UUID
    let role: String
    let content: String
    let timestamp: Date

    init(role: String, content: String) {
        self.id = UUID()
        self.role = role
        self.content = content
        self.timestamp = Date()
    }
}

// MARK: - Phone Contact (from iOS Contacts)
struct PhoneContact: Identifiable {
    let id: String
    let name: String
    let phone: String
}

// MARK: - P2P Message
struct P2PMessage: Identifiable, Codable {
    let id: String
    let fromPhone: String
    let toPhone: String
    let content: String
    let timestamp: Date
    let isRead: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case fromPhone = "from_phone"
        case toPhone = "to_phone"
        case content
        case timestamp
        case isRead = "is_read"
    }
}

// MARK: - Conversation
struct Conversation: Identifiable {
    var id: String { contactPhone }
    let contactPhone: String
    let contactName: String
    let lastMessage: String
    let lastMessageTime: Date
    let unreadCount: Int
}
