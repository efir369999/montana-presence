import SwiftUI

struct ChatsView: View {
    @EnvironmentObject var appState: AppState
    @State private var conversations: [Conversation] = []
    @State private var isLoading = false
    @State private var searchText = ""

    var filteredConversations: [Conversation] {
        if searchText.isEmpty {
            return conversations
        }
        return conversations.filter {
            $0.contactName.localizedCaseInsensitiveContains(searchText) ||
            $0.contactPhone.contains(searchText)
        }
    }

    var body: some View {
        NavigationView {
            ZStack {
                Color("Background").ignoresSafeArea()

                if isLoading {
                    ProgressView()
                        .tint(Color("Gold"))
                } else if conversations.isEmpty {
                    VStack(spacing: 20) {
                        Image(systemName: "bubble.left.and.bubble.right.fill")
                            .font(.system(size: 60))
                            .foregroundColor(.secondary)

                        Text("Нет сообщений")
                            .font(.title2)
                            .foregroundColor(.secondary)

                        Text("Напиши первому контакту из списка")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                } else {
                    List {
                        ForEach(filteredConversations) { conv in
                            NavigationLink(destination: ConversationView(
                                contactPhone: conv.contactPhone,
                                contactName: conv.contactName
                            )) {
                                ConversationRow(conversation: conv)
                            }
                            .listRowBackground(Color("Card"))
                        }
                    }
                    .listStyle(.plain)
                    .searchable(text: $searchText, prompt: "Поиск")
                }
            }
            .navigationTitle("Чаты")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: loadConversations) {
                        Image(systemName: "arrow.clockwise")
                    }
                }
            }
            .onAppear {
                loadConversations()
            }
        }
    }

    private func loadConversations() {
        guard let deviceId = appState.deviceId else { return }
        isLoading = true

        API.shared.getConversations(deviceId: deviceId) { result in
            DispatchQueue.main.async {
                isLoading = false
                switch result {
                case .success(let convs):
                    conversations = convs.sorted { $0.lastMessageTime > $1.lastMessageTime }
                case .failure:
                    break
                }
            }
        }
    }
}

// MARK: - Conversation Row
struct ConversationRow: View {
    let conversation: Conversation

    var body: some View {
        HStack(spacing: 14) {
            // Avatar
            Text(String(conversation.contactName.prefix(1)).uppercased())
                .font(.headline)
                .foregroundColor(Color("Background"))
                .frame(width: 52, height: 52)
                .background(
                    LinearGradient(
                        colors: [Color("Gold"), Color(hex: "FFA500")],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .clipShape(Circle())

            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(conversation.contactName)
                        .font(.body)
                        .fontWeight(.medium)
                        .foregroundColor(.white)

                    Spacer()

                    Text(formatTime(conversation.lastMessageTime))
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                HStack {
                    Text(conversation.lastMessage)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .lineLimit(1)

                    Spacer()

                    if conversation.unreadCount > 0 {
                        Text("\(conversation.unreadCount)")
                            .font(.caption)
                            .fontWeight(.bold)
                            .foregroundColor(Color("Background"))
                            .frame(minWidth: 20, minHeight: 20)
                            .background(Color("Gold"))
                            .clipShape(Circle())
                    }
                }
            }
        }
        .padding(.vertical, 6)
    }

    private func formatTime(_ date: Date) -> String {
        let calendar = Calendar.current
        if calendar.isDateInToday(date) {
            let formatter = DateFormatter()
            formatter.dateFormat = "HH:mm"
            return formatter.string(from: date)
        } else if calendar.isDateInYesterday(date) {
            return "Вчера"
        } else {
            let formatter = DateFormatter()
            formatter.dateFormat = "dd.MM"
            return formatter.string(from: date)
        }
    }
}

// MARK: - Conversation View (P2P Chat)
struct ConversationView: View {
    @EnvironmentObject var appState: AppState
    let contactPhone: String
    let contactName: String

    @State private var messages: [P2PMessage] = []
    @State private var newMessage = ""
    @State private var isLoading = false

    var body: some View {
        ZStack {
            Color("Background").ignoresSafeArea()

            VStack(spacing: 0) {
                // Messages
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 8) {
                            ForEach(messages) { message in
                                MessageBubble(
                                    message: message,
                                    isOutgoing: message.fromPhone != contactPhone
                                )
                                .id(message.id)
                            }
                        }
                        .padding()
                    }
                    .onChange(of: messages.count) { _ in
                        if let lastId = messages.last?.id {
                            withAnimation {
                                proxy.scrollTo(lastId, anchor: .bottom)
                            }
                        }
                    }
                }

                // Input
                HStack(spacing: 12) {
                    TextField("Сообщение...", text: $newMessage)
                        .padding(12)
                        .background(Color("Card"))
                        .cornerRadius(20)

                    Button(action: sendMessage) {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.system(size: 34))
                            .foregroundColor(newMessage.isEmpty ? .secondary : Color("Gold"))
                    }
                    .disabled(newMessage.isEmpty)
                }
                .padding()
                .background(Color("Card").opacity(0.5))
            }
        }
        .navigationTitle(contactName)
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            loadMessages()
        }
    }

    private func loadMessages() {
        guard let deviceId = appState.deviceId else { return }
        isLoading = true

        API.shared.getMessages(deviceId: deviceId, withPhone: contactPhone) { result in
            DispatchQueue.main.async {
                isLoading = false
                switch result {
                case .success(let msgs):
                    messages = msgs.sorted { $0.timestamp < $1.timestamp }
                case .failure:
                    break
                }
            }
        }
    }

    private func sendMessage() {
        guard let deviceId = appState.deviceId, !newMessage.isEmpty else { return }
        let content = newMessage
        newMessage = ""

        API.shared.sendP2PMessage(deviceId: deviceId, toPhone: contactPhone, content: content) { result in
            DispatchQueue.main.async {
                switch result {
                case .success(let message):
                    messages.append(message)
                case .failure:
                    newMessage = content // Restore on failure
                }
            }
        }
    }
}

// MARK: - Message Bubble
struct MessageBubble: View {
    let message: P2PMessage
    let isOutgoing: Bool

    var body: some View {
        HStack {
            if isOutgoing { Spacer() }

            VStack(alignment: isOutgoing ? .trailing : .leading, spacing: 4) {
                Text(message.content)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(isOutgoing ? Color("Gold") : Color("Card"))
                    .foregroundColor(isOutgoing ? Color("Background") : .white)
                    .cornerRadius(18)

                Text(formatTime(message.timestamp))
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: 280, alignment: isOutgoing ? .trailing : .leading)

            if !isOutgoing { Spacer() }
        }
    }

    private func formatTime(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm"
        return formatter.string(from: date)
    }
}
