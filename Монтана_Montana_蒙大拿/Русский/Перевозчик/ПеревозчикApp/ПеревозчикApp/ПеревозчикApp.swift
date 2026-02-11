//
//  ПеревозчикПриложение.swift
//  Перевозчик — Морская Фрахтовая Платформа
//
//  Вход через Telegram @junomontanaagibot
//  B2B для судовладельцев, фрахтователей, брокеров
//

import SwiftUI

@main
struct ПеревозчикПриложение: App {
    @StateObject private var авторизация = СлужбаАвторизации.общий

    var body: some Scene {
        WindowGroup {
            Group {
                if авторизация.авторизован {
                    ГлавныйЭкран()
                } else {
                    ЭкранВхода()
                }
            }
            .preferredColorScheme(.dark)
        }
    }
}

// MARK: - Тема

struct ПеревозчикТема {
    static let фон = Color(hex: "0a0a0f")
    static let карточка = Color(hex: "1a1a2e")
    static let основной = Color(hex: "48dbfb")
    static let вторичный = Color(hex: "feca57")
    static let акцент = Color(hex: "ff6b6b")
    static let успех = Color(hex: "2ecc71")
    static let внимание = Color(hex: "f39c12")
}

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let а, р, г, с: UInt64
        switch hex.count {
        case 6:
            (а, р, г, с) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        default:
            (а, р, г, с) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(р) / 255,
            green: Double(г) / 255,
            blue: Double(с) / 255,
            opacity: Double(а) / 255
        )
    }
}
