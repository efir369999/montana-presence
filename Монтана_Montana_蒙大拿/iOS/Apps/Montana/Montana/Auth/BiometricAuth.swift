//
//  BiometricAuth.swift
//  Junona — Montana Protocol
//
//  Face ID / Touch ID / Device Passcode authentication
//  Native Apple security after cognitive key setup
//
//  "Ключи — это мысли. Лицо — это печать."
//

import Foundation
import LocalAuthentication
import SwiftUI

// MARK: - Biometric Type

enum BiometricType {
    case none
    case touchID
    case faceID
    case opticID  // Vision Pro
    case devicePasscode

    var displayName: String {
        switch self {
        case .none: return "Недоступно"
        case .touchID: return "Touch ID"
        case .faceID: return "Face ID"
        case .opticID: return "Optic ID"
        case .devicePasscode: return "Код устройства"
        }
    }

    var iconName: String {
        switch self {
        case .none: return "lock.slash"
        case .touchID: return "touchid"
        case .faceID: return "faceid"
        case .opticID: return "opticid"
        case .devicePasscode: return "lock.fill"
        }
    }
}

// MARK: - Biometric Auth Service

@MainActor
class BiometricAuth: ObservableObject {
    static let shared = BiometricAuth()

    @Published var isLocked: Bool = true
    @Published var biometricType: BiometricType = .none
    @Published var error: String?

    private let context = LAContext()

    /// Biometric lock is enabled when user has a Passkey (Face ID was set up)
    var isEnabled: Bool {
        UserDefaults.standard.bool(forKey: "montana_has_passkey")
    }

    /// Check if user has set up cognitive key (has private key in keychain)
    var hasIdentity: Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "network.montana.junona",
            kSecAttrAccount as String: "private_key",
            kSecReturnData as String: false
        ]
        return SecItemCopyMatching(query as CFDictionary, nil) == errSecSuccess
    }

    private init() {
        checkBiometricType()

        // If biometric is enabled and user has identity, start locked
        if isEnabled && hasIdentity {
            isLocked = true
        } else {
            isLocked = false
        }
    }

    // MARK: - Check Available Biometric

    func checkBiometricType() {
        let context = LAContext()
        var error: NSError?

        // Check for biometric availability
        if context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) {
            switch context.biometryType {
            case .touchID:
                biometricType = .touchID
            case .faceID:
                biometricType = .faceID
            case .opticID:
                biometricType = .opticID
            default:
                biometricType = .devicePasscode
            }
        } else if context.canEvaluatePolicy(.deviceOwnerAuthentication, error: &error) {
            // Biometric not available but device passcode is
            biometricType = .devicePasscode
        } else {
            biometricType = .none
        }
    }

    // MARK: - Authenticate

    /// Authenticate with Face ID / Touch ID / Device Passcode
    /// Returns true if authentication successful
    func authenticate() async -> Bool {
        guard biometricType != .none else {
            error = "Биометрия недоступна"
            return false
        }

        let context = LAContext()
        context.localizedCancelTitle = "Отмена"
        context.localizedFallbackTitle = "Использовать код"

        let reason = "Разблокируй Montana для доступа к кошельку"

        do {
            // Use deviceOwnerAuthentication to allow both biometric AND passcode fallback
            let success = try await context.evaluatePolicy(
                .deviceOwnerAuthentication,
                localizedReason: reason
            )

            if success {
                isLocked = false
                error = nil
                print("[BiometricAuth] ✅ Authentication successful")
                return true
            } else {
                error = "Аутентификация не удалась"
                return false
            }
        } catch let authError as LAError {
            handleLAError(authError)
            return false
        } catch {
            self.error = "Ошибка аутентификации"
            return false
        }
    }

    // MARK: - Lock

    /// Lock the app (require authentication on next access)
    func lock() {
        guard isEnabled else { return }
        isLocked = true
        print("[BiometricAuth] 🔒 App locked")
    }

    // MARK: - Unlock (for programmatic unlock)

    /// Unlock without authentication (e.g., after passkey removal)
    func unlock() {
        isLocked = false
    }

    // MARK: - Error Handling

    private func handleLAError(_ error: LAError) {
        switch error.code {
        case .userCancel:
            self.error = nil  // User cancelled, no error message
        case .userFallback:
            self.error = nil  // User chose fallback
        case .biometryNotAvailable:
            self.error = "Биометрия недоступна на устройстве"
        case .biometryNotEnrolled:
            self.error = "Настройте Face ID / Touch ID в настройках"
        case .biometryLockout:
            self.error = "Слишком много попыток. Используйте код устройства."
        case .passcodeNotSet:
            self.error = "Установите код-пароль в настройках устройства"
        case .authenticationFailed:
            self.error = "Аутентификация не удалась"
        default:
            self.error = "Ошибка аутентификации"
        }

        print("[BiometricAuth] Error: \(error.localizedDescription)")
    }
}

// MARK: - Lock Screen View

struct LockScreenView: View {
    @ObservedObject var biometricAuth = BiometricAuth.shared
    @State private var isAuthenticating = false

    var body: some View {
        ZStack {
            // Background
            LinearGradient(
                gradient: Gradient(colors: [
                    Color(hex: "0a0a0a"),
                    Color(hex: "1a1a2e")
                ]),
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            VStack(spacing: 40) {
                Spacer()

                // Logo
                Text("🌙")
                    .font(.system(size: 80))

                Text("Montana")
                    .font(.largeTitle)
                    .fontWeight(.bold)
                    .foregroundColor(.white)

                Text("Время — единственная реальная валюта")
                    .font(.subheadline)
                    .foregroundColor(.gray)

                Spacer()

                // Unlock button
                Button(action: {
                    Task {
                        isAuthenticating = true
                        _ = await biometricAuth.authenticate()
                        isAuthenticating = false
                    }
                }) {
                    HStack(spacing: 12) {
                        if isAuthenticating {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        } else {
                            Image(systemName: biometricAuth.biometricType.iconName)
                                .font(.title2)
                        }

                        Text("Разблокировать")
                            .fontWeight(.semibold)
                    }
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: 56)
                    .background(
                        LinearGradient(
                            gradient: Gradient(colors: [
                                Color(hex: "00d4ff"),
                                Color(hex: "7b2fff")
                            ]),
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .cornerRadius(28)
                }
                .disabled(isAuthenticating)
                .padding(.horizontal, 40)

                // Biometric type hint
                Text(biometricAuth.biometricType.displayName)
                    .font(.caption)
                    .foregroundColor(.gray)

                // Error message
                if let error = biometricAuth.error {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.red)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                }

                Spacer()
                    .frame(height: 50)
            }
        }
        .onAppear {
            // Auto-trigger authentication on appear
            Task {
                try? await Task.sleep(nanoseconds: 500_000_000)
                if biometricAuth.isLocked {
                    _ = await biometricAuth.authenticate()
                }
            }
        }
    }
}

// MARK: - Preview

#Preview {
    LockScreenView()
}
