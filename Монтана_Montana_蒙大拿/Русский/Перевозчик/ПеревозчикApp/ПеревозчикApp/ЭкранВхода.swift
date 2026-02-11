//
//  ЭкранВхода.swift
//  Перевозчик — Морская Фрахтовая Платформа
//
//  Авторизация через Telegram
//

import SwiftUI

struct ЭкранВхода: View {
    @ObservedObject private var авторизация = СлужбаАвторизации.общий
    @State private var опросАктивен = false

    var body: some View {
        ZStack {
            ПеревозчикТема.фон.ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()

                // Логотип
                секцияЛоготипа

                Spacer()

                // Контент
                VStack(spacing: 24) {
                    switch авторизация.состояние {
                    case .ожидание:
                        кнопкаТелеграм

                    case .ожиданиеБота:
                        экранОжидания

                    case .проверка:
                        экранПроверки

                    case .ошибка(let сообщение):
                        экранОшибки(сообщение)

                    case .авторизован:
                        EmptyView()
                    }
                }
                .padding(.horizontal, 32)

                Spacer()

                // Подвал
                секцияПодвала
            }
        }
        .onAppear {
            запуститьОпрос()
        }
    }

    // MARK: - Логотип

    private var секцияЛоготипа: some View {
        VStack(spacing: 16) {
            Image("Logo")
                .resizable()
                .scaledToFit()
                .frame(width: 140, height: 140)
                .cornerRadius(20)
                .shadow(color: ПеревозчикТема.основной.opacity(0.3), radius: 15)

            Text("Seafare")
                .font(.system(size: 36, weight: .bold, design: .rounded))
                .foregroundColor(.white)

            Text("B2B для перевозок")
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }

    // MARK: - Кнопка Telegram

    private var кнопкаТелеграм: some View {
        VStack(spacing: 20) {
            Text("Вход по номеру телефона")
                .font(.headline)
                .foregroundColor(.white)

            Button {
                авторизация.открытьБота()
            } label: {
                HStack(spacing: 12) {
                    Image(systemName: "paperplane.fill")
                        .font(.title2)

                    Text("Войти через Telegram")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
                .background(
                    LinearGradient(
                        colors: [Color(hex: "0088cc"), Color(hex: "00aaff")],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .cornerRadius(12)
                .foregroundColor(.white)
            }

            Text("Верификация номера телефона")
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }

    // MARK: - Экран ожидания

    private var экранОжидания: some View {
        VStack(spacing: 20) {
            ProgressView()
                .scaleEffect(1.5)
                .tint(ПеревозчикТема.основной)

            Text("Верификация в Telegram...")
                .font(.headline)
                .foregroundColor(.white)

            VStack(spacing: 8) {
                Image(systemName: "phone.badge.checkmark")
                    .font(.system(size: 40))
                    .foregroundColor(ПеревозчикТема.основной)

                Text("Подтвердите номер телефона\nв боте @junomontanaagibot")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
            .padding()
            .background(ПеревозчикТема.карточка)
            .cornerRadius(12)

            Text("Номер привяжется к вашему аккаунту")
                .font(.caption)
                .foregroundColor(.secondary)

            Button {
                авторизация.открытьБота()
            } label: {
                Text("Открыть Telegram")
                    .font(.subheadline)
                    .foregroundColor(ПеревозчикТема.основной)
            }

            Button {
                авторизация.состояние = .ожидание
            } label: {
                Text("Отмена")
                    .foregroundColor(ПеревозчикТема.акцент)
            }
        }
    }

    // MARK: - Экран проверки

    private var экранПроверки: some View {
        VStack(spacing: 20) {
            ProgressView()
                .scaleEffect(1.5)
                .tint(ПеревозчикТема.основной)

            Text("Проверка...")
                .font(.headline)
                .foregroundColor(.white)
        }
    }

    // MARK: - Экран ошибки

    private func экранОшибки(_ сообщение: String) -> some View {
        VStack(spacing: 20) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 50))
                .foregroundColor(ПеревозчикТема.акцент)

            Text(сообщение)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)

            Button {
                авторизация.состояние = .ожидание
            } label: {
                Text("Попробовать снова")
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
                    .background(ПеревозчикТема.основной)
                    .cornerRadius(12)
                    .foregroundColor(.white)
                    .fontWeight(.semibold)
            }
        }
    }

    // MARK: - Подвал

    private var секцияПодвала: some View {
        Text("Seafare Ɉ")
            .font(.caption2)
            .foregroundColor(.secondary)
            .padding(.bottom, 32)
    }

    // MARK: - Опрос

    private func запуститьОпрос() {
        guard !опросАктивен else { return }
        опросАктивен = true

        Task {
            while опросАктивен {
                if case .ожиданиеБота = авторизация.состояние {
                    await авторизация.проверитьОжидающую()
                }
                try? await Task.sleep(nanoseconds: 3_000_000_000)
            }
        }
    }
}

#Preview {
    ЭкранВхода()
}
