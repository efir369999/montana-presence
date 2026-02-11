//
//  AuthView.swift
//  Junona — Montana Messenger
//
//  Экран авторизации
//

import SwiftUI
import MontanaCore

struct AuthView: View {
    @ObservedObject private var auth = AuthService.shared
    @State private var phone = ""
    @State private var code = ""
    @FocusState private var phoneFocused: Bool
    @FocusState private var codeFocused: Bool

    var body: some View {
        ZStack {
            // Background
            MontanaTheme.background
                .ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()

                // Logo
                VStack(spacing: 16) {
                    ZStack {
                        Circle()
                            .fill(
                                LinearGradient(
                                    colors: [MontanaTheme.primary, MontanaTheme.secondary],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                )
                            )
                            .frame(width: 100, height: 100)

                        Text("Ɉ")
                            .font(.system(size: 50, weight: .bold, design: .rounded))
                            .foregroundColor(.white)
                    }

                    Text("Junona")
                        .font(.system(size: 36, weight: .bold, design: .rounded))
                        .foregroundColor(.white)

                    Text("Мессенджер Монтана")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }

                Spacer()

                // Content based on state
                VStack(spacing: 24) {
                    switch auth.state {
                    case .unauthorized, .sendingCode:
                        phoneInputView

                    case .waitingForCode(let phoneNumber), .verifying(let phoneNumber):
                        codeInputView(phone: phoneNumber)

                    case .creatingKeys:
                        creatingKeysView

                    case .authorized:
                        EmptyView()

                    case .enteringCognitiveKey, .restoringIdentity:
                        // Когнитивный ключ обрабатывается в CognitiveKeyView
                        EmptyView()
                    }

                    // Error
                    if let error = auth.error {
                        Text(error)
                            .font(.caption)
                            .foregroundColor(MontanaTheme.error)
                            .multilineTextAlignment(.center)
                    }
                }
                .padding(.horizontal, 32)

                Spacer()

                // Footer
                VStack(spacing: 8) {
                    Text("Постквантовая криптография ML-DSA-65")
                        .font(.caption2)
                        .foregroundColor(.secondary)

                    Text("Время — единственная реальная валюта")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
                .padding(.bottom, 32)
            }
        }
    }

    // MARK: - Phone Input

    private var phoneInputView: some View {
        VStack(spacing: 20) {
            Text("Введите номер телефона")
                .font(.headline)
                .foregroundColor(.white)

            HStack {
                Text("+7")
                    .foregroundColor(.white)
                    .padding(.leading, 16)

                TextField("999 123 4567", text: $phone)
                    .keyboardType(.phonePad)
                    .textContentType(.telephoneNumber)
                    .foregroundColor(.white)
                    .focused($phoneFocused)
            }
            .padding(.vertical, 16)
            .background(MontanaTheme.cardBackground)
            .cornerRadius(12)

            Button {
                Task {
                    let fullPhone = "+7" + phone.filter { $0.isNumber }
                    await auth.sendCode(to: fullPhone)
                }
            } label: {
                HStack {
                    if auth.state.isSendingCode {
                        ProgressView()
                            .tint(.white)
                    } else {
                        Text("Получить код")
                    }
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
                .background(phone.filter { $0.isNumber }.count >= 10 ? MontanaTheme.primary : MontanaTheme.primary.opacity(0.5))
                .cornerRadius(12)
                .foregroundColor(.white)
                .fontWeight(.semibold)
            }
            .disabled(phone.filter { $0.isNumber }.count < 10 || auth.state.isSendingCode)
        }
        .onAppear {
            phoneFocused = true
        }
        .toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("Готово") {
                    phoneFocused = false
                }
            }
        }
    }

    // MARK: - Code Input

    private func codeInputView(phone: String) -> some View {
        VStack(spacing: 20) {
            Text("Введите код")
                .font(.headline)
                .foregroundColor(.white)

            Text("Код отправлен на \(formatPhone(phone))")
                .font(.subheadline)
                .foregroundColor(.secondary)

            // Code input boxes
            HStack(spacing: 12) {
                ForEach(0..<5, id: \.self) { index in
                    codeDigitBox(at: index)
                }
            }

            // Hidden text field for code input
            TextField("", text: $code)
                .keyboardType(.numberPad)
                .textContentType(.oneTimeCode)
                .focused($codeFocused)
                .frame(width: 1, height: 1)
                .opacity(0.01)
                .onChange(of: code) { _, newValue in
                    // Limit to 5 digits
                    if newValue.count > 5 {
                        code = String(newValue.prefix(5))
                    }
                    // Auto-verify when 5 digits entered
                    if newValue.count == 5 {
                        Task {
                            await auth.verifyCode(newValue, for: phone)
                        }
                    }
                }

            if auth.state.isVerifying {
                ProgressView()
                    .tint(MontanaTheme.primary)
            }

            Button {
                code = ""
                auth.state = .unauthorized
            } label: {
                Text("Изменить номер")
                    .font(.subheadline)
                    .foregroundColor(MontanaTheme.primary)
            }
        }
        .onAppear {
            codeFocused = true
        }
        .onTapGesture {
            codeFocused = true
        }
        .toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("Готово") {
                    codeFocused = false
                }
            }
        }
    }

    private func codeDigitBox(at index: Int) -> some View {
        let digit = index < code.count ? String(code[code.index(code.startIndex, offsetBy: index)]) : ""

        return Text(digit)
            .font(.system(size: 24, weight: .bold, design: .monospaced))
            .foregroundColor(.white)
            .frame(width: 50, height: 60)
            .background(MontanaTheme.cardBackground)
            .cornerRadius(12)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(index == code.count ? MontanaTheme.primary : Color.clear, lineWidth: 2)
            )
    }

    // MARK: - Creating Keys

    private var creatingKeysView: some View {
        VStack(spacing: 20) {
            ProgressView()
                .scaleEffect(1.5)
                .tint(MontanaTheme.primary)

            Text("Генерация ключей...")
                .font(.headline)
                .foregroundColor(.white)

            Text("ML-DSA-65 (FIPS 204)\nПостквантовая криптография")
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
    }

    // MARK: - Helpers

    private func formatPhone(_ phone: String) -> String {
        let digits = phone.filter { $0.isNumber }
        if digits.count >= 11 {
            let code = String(digits.prefix(1))
            let area = String(digits.dropFirst().prefix(3))
            let part1 = String(digits.dropFirst(4).prefix(3))
            let part2 = String(digits.dropFirst(7).prefix(2))
            let part3 = String(digits.dropFirst(9).prefix(2))
            return "+\(code) (\(area)) \(part1)-\(part2)-\(part3)"
        }
        return phone
    }
}

#Preview {
    AuthView()
}
