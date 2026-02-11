//
//  СлужбаАвторизации.swift
//  Перевозчик — Морская Фрахтовая Платформа
//
//  Вход через Telegram @junomontanaagibot
//

import SwiftUI
import Foundation

// MARK: - Состояние авторизации

enum СостояниеАвторизации {
    case ожидание
    case ожиданиеБота
    case проверка(код: String)
    case авторизован
    case ошибка(String)
}

// MARK: - Модель пользователя

struct Пользователь: Codable, Identifiable {
    let id: String
    let телеграмИд: Int64
    let юзернейм: String?
    let имя: String
    let фамилия: String?
    let роль: Роль
    let компания: String?
    let верифицирован: Bool
    let датаСоздания: String  // ISO8601 string
    let mtАдрес: String?
    let телефон: String?

    enum Роль: String, Codable {
        case судовладелец = "судовладелец"
        case фрахтователь = "фрахтователь"
        case брокер = "брокер"
        case агент = "агент"
    }

    var полноеИмя: String {
        if let фамилия = фамилия {
            return "\(имя) \(фамилия)"
        }
        return имя
    }

    var названиеРоли: String {
        switch роль {
        case .судовладелец: return "Судовладелец"
        case .фрахтователь: return "Фрахтователь"
        case .брокер: return "Брокер"
        case .агент: return "Агент"
        }
    }

    var короткийАдрес: String {
        guard let адрес = mtАдрес, адрес.count > 12 else {
            return mtАдрес ?? "—"
        }
        return String(адрес.prefix(8)) + "..." + String(адрес.suffix(4))
    }

    // Для Codable
    enum CodingKeys: String, CodingKey {
        case id
        case телеграмИд = "telegram_id"
        case юзернейм = "username"
        case имя = "first_name"
        case фамилия = "last_name"
        case роль = "role"
        case компания = "company"
        case верифицирован = "verified"
        case датаСоздания = "created_at"
        case mtАдрес = "mt_address"
        case телефон = "phone"
    }
}

// MARK: - Служба авторизации

@MainActor
class СлужбаАвторизации: ObservableObject {
    static let общий = СлужбаАвторизации()

    @Published var состояние: СостояниеАвторизации = .ожидание
    @Published var пользователь: Пользователь?
    @Published var кодАвторизации: String = ""

    private let ботЮзернейм = "junomontanaagibot"
    private let базовыйURL = "https://amsterdam.montana.network"

    // Демо режим
    private let демоРежим = true
    private let демоКод = "SEAFARE2026"

    var авторизован: Bool {
        if case .авторизован = состояние { return true }
        return false
    }

    private init() {
        // Проверка сохранённой сессии
        if let данные = UserDefaults.standard.data(forKey: "перевозчик_пользователь"),
           let сохранённый = try? JSONDecoder().decode(Пользователь.self, from: данные) {
            self.пользователь = сохранённый
            self.состояние = .авторизован
        }
    }

    // MARK: - Генерация кода

    func сгенерироватьКод() -> String {
        let символы = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        let код = String((0..<6).map { _ in символы.randomElement()! })
        кодАвторизации = код
        return код
    }

    // MARK: - Открыть Telegram бота

    func открытьБота() {
        let код = сгенерироватьКод()
        состояние = .ожиданиеБота

        let ссылка = "https://t.me/\(ботЮзернейм)?start=seafare_\(код)"

        if let url = URL(string: ссылка) {
            UIApplication.shared.open(url)
        }
    }

    // MARK: - Проверка кода

    func проверитьКод(_ введённыйКод: String) async {
        состояние = .проверка(код: введённыйКод)

        // Демо режим
        if демоРежим {
            try? await Task.sleep(nanoseconds: 1_000_000_000)

            if введённыйКод.uppercased() == демоКод || введённыйКод.uppercased() == кодАвторизации {
                let новыйПользователь = Пользователь(
                    id: UUID().uuidString,
                    телеграмИд: 123456789,
                    юзернейм: "demo_user",
                    имя: "Demo",
                    фамилия: "User",
                    роль: .брокер,
                    компания: "Seafare",
                    верифицирован: true,
                    датаСоздания: ISO8601DateFormatter().string(from: Date()),
                    mtАдрес: "mt" + UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(40),
                    телефон: "+7 (000) 000-00-00"
                )

                сохранитьПользователя(новыйПользователь)
                пользователь = новыйПользователь
                состояние = .авторизован
            } else {
                состояние = .ошибка("Неверный код. Демо: \(демоКод)")
            }
            return
        }

        // Реальная проверка через сервер
        do {
            let запрос = ЗапросПроверки(код: введённыйКод)
            let ответ: ОтветПроверки = try await отправить("/api/v1/перевозчик/проверка", тело: запрос)

            if ответ.успех, let юзер = ответ.пользователь {
                сохранитьПользователя(юзер)
                пользователь = юзер
                состояние = .авторизован
            } else {
                состояние = .ошибка(ответ.ошибка ?? "Ошибка верификации")
            }
        } catch {
            состояние = .ошибка("Сеть недоступна")
        }
    }

    // MARK: - Проверка ожидающей авторизации

    func проверитьОжидающую() async {
        guard !кодАвторизации.isEmpty else { return }

        do {
            let ответ: ОтветПроверкиСтатуса = try await получить("/api/v1/перевозчик/статус/\(кодАвторизации)")

            if ответ.авторизован, let юзер = ответ.пользователь {
                сохранитьПользователя(юзер)
                пользователь = юзер
                состояние = .авторизован
            }
        } catch {
            // Тихая ошибка, продолжаем опрос
        }
    }

    // MARK: - Выход

    func выйти() {
        UserDefaults.standard.removeObject(forKey: "перевозчик_пользователь")
        UserDefaults.standard.removeObject(forKey: "перевозчик_токен")
        пользователь = nil
        состояние = .ожидание
        кодАвторизации = ""
    }

    // MARK: - Сохранение

    private func сохранитьПользователя(_ юзер: Пользователь) {
        if let данные = try? JSONEncoder().encode(юзер) {
            UserDefaults.standard.set(данные, forKey: "перевозчик_пользователь")
        }
    }

    // MARK: - Сеть

    private func отправить<Т: Encodable, О: Decodable>(_ путь: String, тело: Т) async throws -> О {
        guard let url = URL(string: базовыйURL + путь) else {
            throw URLError(.badURL)
        }

        var запрос = URLRequest(url: url)
        запрос.httpMethod = "POST"
        запрос.setValue("application/json", forHTTPHeaderField: "Content-Type")
        запрос.httpBody = try JSONEncoder().encode(тело)

        let (данные, _) = try await URLSession.shared.data(for: запрос)
        return try JSONDecoder().decode(О.self, from: данные)
    }

    private func получить<О: Decodable>(_ путь: String) async throws -> О {
        guard let url = URL(string: базовыйURL + путь) else {
            throw URLError(.badURL)
        }

        let (данные, _) = try await URLSession.shared.data(from: url)
        return try JSONDecoder().decode(О.self, from: данные)
    }
}

// MARK: - Модели API

struct ЗапросПроверки: Encodable {
    let код: String

    enum CodingKeys: String, CodingKey {
        case код = "code"
    }
}

struct ОтветПроверки: Decodable {
    let успех: Bool
    let пользователь: Пользователь?
    let ошибка: String?

    enum CodingKeys: String, CodingKey {
        case успех = "success"
        case пользователь = "user"
        case ошибка = "error"
    }
}

struct ОтветПроверкиСтатуса: Decodable {
    let авторизован: Bool
    let пользователь: Пользователь?

    enum CodingKeys: String, CodingKey {
        case авторизован = "authorized"
        case пользователь = "user"
    }
}
