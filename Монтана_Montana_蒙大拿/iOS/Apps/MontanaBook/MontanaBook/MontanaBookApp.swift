//
//  MontanaBookApp.swift
//  Книга Монтана — Аудиокнига и Читалка
//
//  "Время — единственная реальная валюта"
//

import SwiftUI
import AVFoundation

@main
struct MontanaBookApp: App {
    @StateObject private var audioPlayer = AudioPlayer()
    @StateObject private var bookStore = BookStore()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(audioPlayer)
                .environmentObject(bookStore)
                .preferredColorScheme(.dark)
        }
    }
}

// MARK: - Content View

struct ContentView: View {
    @EnvironmentObject var bookStore: BookStore
    @EnvironmentObject var audioPlayer: AudioPlayer
    @State private var selectedChapter: Chapter?

    var body: some View {
        NavigationStack {
            ZStack {
                // Background
                LinearGradient(
                    colors: [Color(hex: "0a0a0a"), Color(hex: "1a1a2e")],
                    startPoint: .top,
                    endPoint: .bottom
                )
                .ignoresSafeArea()

                VStack(spacing: 0) {
                    // Chapter List
                    ScrollView {
                        LazyVStack(spacing: 12) {
                            ForEach(bookStore.chapters) { chapter in
                                ChapterRow(chapter: chapter)
                                    .onTapGesture {
                                        selectedChapter = chapter
                                    }
                            }
                        }
                        .padding()
                    }

                    // Mini Player
                    if audioPlayer.currentChapter != nil {
                        MiniPlayerView()
                            .transition(.move(edge: .bottom))
                    }
                }
            }
            .navigationTitle("Книга Монтана")
            .sheet(item: $selectedChapter) { chapter in
                ChapterDetailView(chapter: chapter)
            }
        }
    }
}

// MARK: - Chapter Model

struct Chapter: Identifiable, Hashable {
    let id: String
    let number: Int
    let title: String
    let textURL: URL?
    let audioURL: URL?

    var displayTitle: String {
        if number == 0 {
            return "Прелюдия"
        }
        return "\(number). \(title)"
    }

    var hasAudio: Bool {
        audioURL != nil
    }
}

// MARK: - Book Store

class BookStore: ObservableObject {
    @Published var chapters: [Chapter] = []

    init() {
        loadChapters()
    }

    func loadChapters() {
        // Hardcoded chapters from the book
        let chapterData: [(Int, String)] = [
            (0, "ПРЕЛЮДИЯ"),
            (1, "Симуляция"),
            (2, "Унижение"),
            (3, "Поток"),
            (4, "Следы"),
            (5, "Тревоги"),
            (6, "День Юноны"),
            (7, "Печать Времени"),
            (8, "Пять Узлов"),
            (9, "Комедия"),
            (10, "Порядок"),
            (11, "ДНК"),
            (12, "Отдохнул"),
            (13, "Возрождение"),
            (14, "Архитектор"),
            (15, "Крещение"),
            (16, "Ничто"),
            (17, "Ирония"),
            (18, "Дом"),
            (19, "Сёстры"),
            (20, "Тишина"),
            (21, "Развилка"),
            (22, "Начало"),
            (23, "Отпуск")
        ]

        chapters = chapterData.map { number, title in
            let prefix = number == 0 ? "00" : String(format: "%02d", number)
            let fileName = "\(prefix). \(title)"

            return Chapter(
                id: "\(number)",
                number: number,
                title: title,
                textURL: Bundle.main.url(forResource: fileName, withExtension: "md"),
                audioURL: Bundle.main.url(forResource: fileName, withExtension: "mp3")
            )
        }
    }

    func loadChapterText(_ chapter: Chapter) -> String {
        guard let url = chapter.textURL else {
            return "Текст недоступен"
        }

        do {
            let content = try String(contentsOf: url, encoding: .utf8)
            // Remove markdown formatting for display
            return cleanMarkdown(content)
        } catch {
            return "Ошибка загрузки: \(error.localizedDescription)"
        }
    }

    private func cleanMarkdown(_ text: String) -> String {
        var result = text
        // Remove headers
        result = result.replacingOccurrences(of: "^#{1,6}\\s*", with: "", options: .regularExpression)
        // Remove bold/italic
        result = result.replacingOccurrences(of: "\\*\\*(.+?)\\*\\*", with: "$1", options: .regularExpression)
        result = result.replacingOccurrences(of: "\\*(.+?)\\*", with: "$1", options: .regularExpression)
        // Remove links
        result = result.replacingOccurrences(of: "\\[(.+?)\\]\\(.+?\\)", with: "$1", options: .regularExpression)
        return result
    }
}

// MARK: - Audio Player

class AudioPlayer: ObservableObject {
    @Published var currentChapter: Chapter?
    @Published var isPlaying = false
    @Published var progress: Double = 0
    @Published var duration: Double = 0
    @Published var currentTime: Double = 0

    private var player: AVAudioPlayer?
    private var timer: Timer?

    init() {
        setupAudioSession()
    }

    private func setupAudioSession() {
        do {
            try AVAudioSession.sharedInstance().setCategory(.playback, mode: .spokenAudio)
            try AVAudioSession.sharedInstance().setActive(true)
        } catch {
            print("Audio session error: \(error)")
        }
    }

    func play(_ chapter: Chapter) {
        guard let url = chapter.audioURL else { return }

        do {
            player = try AVAudioPlayer(contentsOf: url)
            player?.prepareToPlay()
            player?.play()

            currentChapter = chapter
            isPlaying = true
            duration = player?.duration ?? 0

            startTimer()
        } catch {
            print("Playback error: \(error)")
        }
    }

    func togglePlayPause() {
        guard let player = player else { return }

        if player.isPlaying {
            player.pause()
            isPlaying = false
        } else {
            player.play()
            isPlaying = true
        }
    }

    func seek(to time: Double) {
        player?.currentTime = time
        currentTime = time
    }

    func skipForward(_ seconds: Double = 15) {
        let newTime = min((player?.currentTime ?? 0) + seconds, duration)
        seek(to: newTime)
    }

    func skipBackward(_ seconds: Double = 15) {
        let newTime = max((player?.currentTime ?? 0) - seconds, 0)
        seek(to: newTime)
    }

    private func startTimer() {
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            guard let self = self, let player = self.player else { return }
            self.currentTime = player.currentTime
            self.progress = player.currentTime / player.duration
        }
    }

    func stop() {
        player?.stop()
        timer?.invalidate()
        isPlaying = false
        currentChapter = nil
    }
}

// MARK: - Chapter Row

struct ChapterRow: View {
    let chapter: Chapter
    @EnvironmentObject var audioPlayer: AudioPlayer

    var isPlaying: Bool {
        audioPlayer.currentChapter?.id == chapter.id && audioPlayer.isPlaying
    }

    var body: some View {
        HStack(spacing: 16) {
            // Number
            ZStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [Color(hex: "00d4ff"), Color(hex: "7b2fff")],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 44, height: 44)

                if isPlaying {
                    Image(systemName: "waveform")
                        .font(.system(size: 18))
                        .foregroundColor(.white)
                } else {
                    Text(chapter.number == 0 ? "П" : "\(chapter.number)")
                        .font(.system(size: 18, weight: .bold))
                        .foregroundColor(.white)
                }
            }

            // Title
            VStack(alignment: .leading, spacing: 4) {
                Text(chapter.displayTitle)
                    .font(.headline)
                    .foregroundColor(.white)

                HStack(spacing: 8) {
                    if chapter.hasAudio {
                        Label("Аудио", systemImage: "headphones")
                            .font(.caption)
                            .foregroundColor(Color(hex: "00d4ff"))
                    }

                    Label("Текст", systemImage: "doc.text")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            Spacer()

            Image(systemName: "chevron.right")
                .foregroundColor(.secondary)
        }
        .padding()
        .background(Color(hex: "1a1a2e").opacity(0.8))
        .cornerRadius(12)
    }
}

// MARK: - Chapter Detail View

struct ChapterDetailView: View {
    let chapter: Chapter
    @EnvironmentObject var audioPlayer: AudioPlayer
    @EnvironmentObject var bookStore: BookStore
    @Environment(\.dismiss) var dismiss
    @State private var showingReader = false

    var body: some View {
        NavigationStack {
            ZStack {
                LinearGradient(
                    colors: [Color(hex: "0a0a0a"), Color(hex: "1a1a2e")],
                    startPoint: .top,
                    endPoint: .bottom
                )
                .ignoresSafeArea()

                VStack(spacing: 32) {
                    // Cover
                    ZStack {
                        RoundedRectangle(cornerRadius: 20)
                            .fill(
                                LinearGradient(
                                    colors: [Color(hex: "00d4ff"), Color(hex: "7b2fff")],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                )
                            )
                            .frame(width: 200, height: 200)

                        VStack(spacing: 8) {
                            Text("Ɉ")
                                .font(.system(size: 60, weight: .bold))
                                .foregroundColor(.white)

                            Text("MONTANA")
                                .font(.caption)
                                .fontWeight(.bold)
                                .foregroundColor(.white.opacity(0.8))
                        }
                    }
                    .shadow(color: Color(hex: "7b2fff").opacity(0.5), radius: 20)

                    // Title
                    VStack(spacing: 8) {
                        Text(chapter.displayTitle)
                            .font(.title)
                            .fontWeight(.bold)
                            .foregroundColor(.white)

                        Text("Книга Монтана")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }

                    Spacer()

                    // Audio Player Controls
                    if chapter.hasAudio {
                        AudioPlayerControls(chapter: chapter)
                    }

                    // Read Button
                    Button {
                        showingReader = true
                    } label: {
                        HStack {
                            Image(systemName: "book.fill")
                            Text("Читать")
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color(hex: "1a1a2e"))
                        .foregroundColor(.white)
                        .cornerRadius(12)
                    }
                    .padding(.horizontal)
                    .padding(.bottom)
                }
                .padding(.top, 40)
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Закрыть") {
                        dismiss()
                    }
                }
            }
            .sheet(isPresented: $showingReader) {
                ReaderView(chapter: chapter)
            }
        }
    }
}

// MARK: - Audio Player Controls

struct AudioPlayerControls: View {
    let chapter: Chapter
    @EnvironmentObject var audioPlayer: AudioPlayer

    var isCurrentChapter: Bool {
        audioPlayer.currentChapter?.id == chapter.id
    }

    var body: some View {
        VStack(spacing: 20) {
            // Progress
            if isCurrentChapter {
                VStack(spacing: 8) {
                    Slider(value: Binding(
                        get: { audioPlayer.progress },
                        set: { audioPlayer.seek(to: $0 * audioPlayer.duration) }
                    ))
                    .tint(Color(hex: "00d4ff"))

                    HStack {
                        Text(formatTime(audioPlayer.currentTime))
                        Spacer()
                        Text(formatTime(audioPlayer.duration))
                    }
                    .font(.caption)
                    .foregroundColor(.secondary)
                }
                .padding(.horizontal)
            }

            // Controls
            HStack(spacing: 40) {
                Button {
                    audioPlayer.skipBackward()
                } label: {
                    Image(systemName: "gobackward.15")
                        .font(.title)
                        .foregroundColor(.white)
                }
                .opacity(isCurrentChapter ? 1 : 0.5)
                .disabled(!isCurrentChapter)

                Button {
                    if isCurrentChapter {
                        audioPlayer.togglePlayPause()
                    } else {
                        audioPlayer.play(chapter)
                    }
                } label: {
                    ZStack {
                        Circle()
                            .fill(
                                LinearGradient(
                                    colors: [Color(hex: "00d4ff"), Color(hex: "7b2fff")],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                )
                            )
                            .frame(width: 64, height: 64)

                        Image(systemName: isCurrentChapter && audioPlayer.isPlaying ? "pause.fill" : "play.fill")
                            .font(.title)
                            .foregroundColor(.white)
                    }
                }

                Button {
                    audioPlayer.skipForward()
                } label: {
                    Image(systemName: "goforward.15")
                        .font(.title)
                        .foregroundColor(.white)
                }
                .opacity(isCurrentChapter ? 1 : 0.5)
                .disabled(!isCurrentChapter)
            }
        }
    }

    private func formatTime(_ time: Double) -> String {
        let minutes = Int(time) / 60
        let seconds = Int(time) % 60
        return String(format: "%d:%02d", minutes, seconds)
    }
}

// MARK: - Mini Player View

struct MiniPlayerView: View {
    @EnvironmentObject var audioPlayer: AudioPlayer

    var body: some View {
        HStack(spacing: 16) {
            // Chapter info
            if let chapter = audioPlayer.currentChapter {
                ZStack {
                    Circle()
                        .fill(
                            LinearGradient(
                                colors: [Color(hex: "00d4ff"), Color(hex: "7b2fff")],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .frame(width: 40, height: 40)

                    Text("Ɉ")
                        .font(.system(size: 20, weight: .bold))
                        .foregroundColor(.white)
                }

                VStack(alignment: .leading) {
                    Text(chapter.displayTitle)
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(.white)

                    Text("Книга Монтана")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            Spacer()

            // Controls
            Button {
                audioPlayer.togglePlayPause()
            } label: {
                Image(systemName: audioPlayer.isPlaying ? "pause.fill" : "play.fill")
                    .font(.title2)
                    .foregroundColor(.white)
            }

            Button {
                audioPlayer.stop()
            } label: {
                Image(systemName: "xmark")
                    .font(.title3)
                    .foregroundColor(.secondary)
            }
        }
        .padding()
        .background(Color(hex: "1a1a2e"))
    }
}

// MARK: - Reader View

struct ReaderView: View {
    let chapter: Chapter
    @EnvironmentObject var bookStore: BookStore
    @Environment(\.dismiss) var dismiss
    @State private var text = ""
    @State private var fontSize: CGFloat = 18

    var body: some View {
        NavigationStack {
            ZStack {
                Color(hex: "0a0a0a")
                    .ignoresSafeArea()

                ScrollView {
                    Text(text)
                        .font(.system(size: fontSize))
                        .foregroundColor(.white.opacity(0.9))
                        .lineSpacing(8)
                        .padding()
                }
            }
            .navigationTitle(chapter.displayTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Закрыть") {
                        dismiss()
                    }
                }

                ToolbarItem(placement: .navigationBarTrailing) {
                    Menu {
                        Button {
                            fontSize = max(14, fontSize - 2)
                        } label: {
                            Label("Меньше", systemImage: "textformat.size.smaller")
                        }

                        Button {
                            fontSize = min(28, fontSize + 2)
                        } label: {
                            Label("Больше", systemImage: "textformat.size.larger")
                        }
                    } label: {
                        Image(systemName: "textformat.size")
                    }
                }
            }
            .onAppear {
                text = bookStore.loadChapterText(chapter)
            }
        }
    }
}

// MARK: - Color Extension

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3:
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6:
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8:
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (1, 1, 1, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

#Preview {
    ContentView()
        .environmentObject(AudioPlayer())
        .environmentObject(BookStore())
}
