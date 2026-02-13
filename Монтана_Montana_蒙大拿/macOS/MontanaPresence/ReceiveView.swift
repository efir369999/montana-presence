import SwiftUI
import CoreImage.CIFilterBuiltins

struct ReceiveView: View {
    @EnvironmentObject var engine: PresenceEngine
    @State private var copiedNumber = false
    @State private var copiedFull = false
    @Environment(\.dismiss) private var dismiss

    private let cyan = Color(red: 0, green: 0.83, blue: 1)
    private let cardBg = Color(red: 0.09, green: 0.09, blue: 0.12)
    private let gold = Color(red: 0.85, green: 0.68, blue: 0.25)

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Image(systemName: "arrow.down.circle.fill")
                    .foregroundColor(cyan)
                Text("\u{0248} \u{041f}\u{043e}\u{043b}\u{0443}\u{0447}\u{0438}\u{0442}\u{044c}")
                    .font(.system(size: 16, weight: .bold))
                Spacer()
                Button(action: { dismiss() }) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 16)
            .padding(.top, 14)
            .padding(.bottom, 10)

            let walletNum = UserDefaults.standard.integer(forKey: "wallet_number")

            // Alias + copy number button
            if walletNum > 0 {
                VStack(spacing: 6) {
                    Text("\u{0248}-\(walletNum)")
                        .font(.system(size: 36, weight: .bold, design: .monospaced))
                        .foregroundColor(gold)
                        .textSelection(.enabled)

                    Button(action: {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString("\(walletNum)", forType: .string)
                        copiedNumber = true
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { copiedNumber = false }
                    }) {
                        HStack(spacing: 4) {
                            Image(systemName: copiedNumber ? "checkmark" : "doc.on.doc")
                                .font(.system(size: 10))
                            Text(copiedNumber ? "\u{0421}\u{043a}\u{043e}\u{043f}\u{0438}\u{0440}\u{043e}\u{0432}\u{0430}\u{043d}\u{043e}!" : "\u{041a}\u{043e}\u{043f}\u{0438}\u{0440}\u{043e}\u{0432}\u{0430}\u{0442}\u{044c} \u{043d}\u{043e}\u{043c}\u{0435}\u{0440}")
                                .font(.system(size: 11, weight: .medium))
                        }
                        .foregroundColor(copiedNumber ? .green : cyan)
                    }
                    .buttonStyle(.plain)

                    Text("\u{041d}\u{0430}\u{0437}\u{043e}\u{0432}\u{0438}\u{0442}\u{0435} \u{043d}\u{043e}\u{043c}\u{0435}\u{0440} \u{043e}\u{0442}\u{043f}\u{0440}\u{0430}\u{0432}\u{0438}\u{0442}\u{0435}\u{043b}\u{044e}")
                        .font(.system(size: 10))
                        .foregroundColor(.secondary)
                }
                .padding(.bottom, 12)
            }

            // QR code
            if let addr = engine.address, !addr.isEmpty {
                let qrString = walletNum > 0 ? "\(walletNum)" : addr
                if let qrImage = generateQR(from: qrString) {
                    Image(nsImage: qrImage)
                        .resizable()
                        .interpolation(.none)
                        .frame(width: 150, height: 150)
                        .background(Color.white)
                        .cornerRadius(8)
                        .padding(.bottom, 12)
                }
            }

            // Full address card
            if let addr = engine.address {
                VStack(spacing: 8) {
                    Text(addr)
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity)

                    Button(action: {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(addr, forType: .string)
                        copiedFull = true
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { copiedFull = false }
                    }) {
                        HStack(spacing: 4) {
                            Image(systemName: copiedFull ? "checkmark" : "rectangle.on.rectangle")
                                .font(.system(size: 10))
                            Text(copiedFull ? "\u{0421}\u{043a}\u{043e}\u{043f}\u{0438}\u{0440}\u{043e}\u{0432}\u{0430}\u{043d}\u{043e}!" : "\u{041a}\u{043e}\u{043f}\u{0438}\u{0440}\u{043e}\u{0432}\u{0430}\u{0442}\u{044c} \u{0430}\u{0434}\u{0440}\u{0435}\u{0441}")
                                .font(.system(size: 11, weight: .medium))
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .tint(copiedFull ? .green : .secondary)
                    .controlSize(.small)
                }
                .padding(12)
                .background(cardBg)
                .cornerRadius(8)
                .padding(.horizontal, 16)
            }

            Spacer()
        }
        .frame(width: 280, height: walletNumValue > 0 ? 430 : 370)
    }

    private var walletNumValue: Int {
        UserDefaults.standard.integer(forKey: "wallet_number")
    }

    private func generateQR(from string: String) -> NSImage? {
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(string.utf8)
        filter.correctionLevel = "M"

        guard let ciImage = filter.outputImage else { return nil }
        let scaled = ciImage.transformed(by: CGAffineTransform(scaleX: 10, y: 10))

        let rep = NSCIImageRep(ciImage: scaled)
        let nsImage = NSImage(size: rep.size)
        nsImage.addRepresentation(rep)
        return nsImage
    }
}
