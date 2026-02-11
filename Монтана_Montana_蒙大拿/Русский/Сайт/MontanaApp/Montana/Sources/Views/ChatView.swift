import SwiftUI

struct ChatView: View {
    @EnvironmentObject var appState: AppState
    @State private var messages: [ChatMessage] = []
    @State private var inputText = ""
    @State private var isLoading = false
    @FocusState private var isInputFocused: Bool

    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Messages
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 12) {
                            ForEach(messages) { message in
                                MessageBubble(message: message)
                                    .id(message.id)
                            }

                            if isLoading {
                                HStack {
                                    TypingIndicator()
                                    Spacer()
                                }
                                .padding(.horizontal)
                            }
                        }
                        .padding()
                    }
                    .onChange(of: messages.count) { _ in
                        if let last = messages.last {
                            withAnimation {
                                proxy.scrollTo(last.id, anchor: .bottom)
                            }
                        }
                    }
                }

                // Input
                HStack(spacing: 12) {
                    TextField("Сообщение...", text: $inputText)
                        .padding(12)
                        .background(Color("Card"))
                        .cornerRadius(20)
                        .focused($isInputFocused)

                    Button(action: sendMessage) {
                        Image(systemName: "arrow.up")
                            .fontWeight(.semibold)
                            .foregroundColor(Color("Background"))
                            .frame(width: 40, height: 40)
                            .background(Color("Gold"))
                            .clipShape(Circle())
                    }
                    .disabled(inputText.trimmingCharacters(in: .whitespaces).isEmpty || isLoading)
                }
                .padding()
                .background(Color("Background"))
            }
            .background(Color("Background").ignoresSafeArea())
            .navigationTitle("Юнона ☀️")
            .onAppear {
                if messages.isEmpty {
                    // Welcome message
                    messages.append(ChatMessage(
                        role: "assistant",
                        content: "Привет! Я Юнона ☀️\n\nЯ AI ассистент Montana Protocol. Могу помочь с переводами, рассказать о протоколе или просто поговорить.\n\nО чём хочешь поговорить?"
                    ))
                }
            }
        }
    }

    private func sendMessage() {
        let text = inputText.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty else { return }

        // Add user message
        messages.append(ChatMessage(role: "user", content: text))
        inputText = ""
        isLoading = true

        // Send to API
        guard let deviceId = UserDefaults.standard.string(forKey: "deviceId") else {
            messages.append(ChatMessage(role: "assistant", content: "Ошибка: не авторизован"))
            isLoading = false
            return
        }

        API.shared.sendMessage(deviceId: deviceId, message: text) { result in
            DispatchQueue.main.async {
                isLoading = false
                switch result {
                case .success(let response):
                    messages.append(ChatMessage(role: "assistant", content: response))
                case .failure:
                    messages.append(ChatMessage(role: "assistant", content: "Ошибка соединения. Попробуй позже."))
                }
            }
        }
    }
}

// MARK: - Message Bubble
struct MessageBubble: View {
    let message: ChatMessage

    var isUser: Bool { message.role == "user" }

    var body: some View {
        HStack {
            if isUser { Spacer() }

            Text(message.content)
                .padding(12)
                .background(
                    isUser ?
                    LinearGradient(colors: [Color("Gold"), Color(hex: "FFA500")], startPoint: .leading, endPoint: .trailing) :
                    LinearGradient(colors: [Color("Card"), Color("Card")], startPoint: .leading, endPoint: .trailing)
                )
                .foregroundColor(isUser ? Color("Background") : .white)
                .cornerRadius(18)
                .cornerRadius(isUser ? 4 : 18, corners: isUser ? .bottomRight : .bottomLeft)

            if !isUser { Spacer() }
        }
    }
}

// MARK: - Typing Indicator
struct TypingIndicator: View {
    @State private var animating = false

    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<3) { i in
                Circle()
                    .fill(Color.secondary)
                    .frame(width: 8, height: 8)
                    .scaleEffect(animating ? 1 : 0.5)
                    .animation(
                        .easeInOut(duration: 0.6)
                        .repeatForever()
                        .delay(Double(i) * 0.2),
                        value: animating
                    )
            }
        }
        .padding(12)
        .background(Color("Card"))
        .cornerRadius(18)
        .onAppear { animating = true }
    }
}

// MARK: - Corner Radius Extension
extension View {
    func cornerRadius(_ radius: CGFloat, corners: UIRectCorner) -> some View {
        clipShape(RoundedCorner(radius: radius, corners: corners))
    }
}

struct RoundedCorner: Shape {
    var radius: CGFloat = .infinity
    var corners: UIRectCorner = .allCorners

    func path(in rect: CGRect) -> Path {
        let path = UIBezierPath(
            roundedRect: rect,
            byRoundingCorners: corners,
            cornerRadii: CGSize(width: radius, height: radius)
        )
        return Path(path.cgPath)
    }
}
