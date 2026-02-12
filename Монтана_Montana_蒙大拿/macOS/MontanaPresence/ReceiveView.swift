import SwiftUI
import CoreImage.CIFilterBuiltins

struct ReceiveView: View {
    @EnvironmentObject var engine: PresenceEngine
    @State private var copiedAlias = false
    @State private var copiedFull = false
    @Environment(\.dismiss) private var dismiss

    private let cyan = Color(red: 0, green: 0.83, blue: 1)

    var body: some View {
        VStack(spacing: 16) {
            HStack {
                Text("\u{0248} Получить")
                    .font(.system(size: 16, weight: .bold))
                Spacer()
                Button(action: { dismiss() }) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
            }

            let walletNum = UserDefaults.standard.integer(forKey: "wallet_number")
            if walletNum > 0 {
                Text("\u{0248}-\(walletNum)")
                    .font(.system(size: 36, weight: .bold, design: .monospaced))
                    .foregroundColor(cyan)
                    .textSelection(.enabled)

                Text("Назовите номер отправителю или нажмите Копировать")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }

            Divider()

            if let addr = engine.address, !addr.isEmpty {
                let qrString = walletNum > 0 ? "\(walletNum)" : addr
                if let qrImage = generateQR(from: qrString) {
                    Image(nsImage: qrImage)
                        .resizable()
                        .interpolation(.none)
                        .frame(width: 160, height: 160)
                        .background(Color.white)
                        .cornerRadius(8)
                }
            }

            Divider()

            if let addr = engine.address {
                VStack(spacing: 8) {
                    Text(addr)
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .textSelection(.enabled)

                    if walletNum > 0 {
                        Button(action: {
                            NSPasteboard.general.clearContents()
                            NSPasteboard.general.setString("\(walletNum)", forType: .string)
                            copiedAlias = true
                            DispatchQueue.main.asyncAfter(deadline: .now() + 2) { copiedAlias = false }
                        }) {
                            HStack {
                                Image(systemName: copiedAlias ? "checkmark" : "doc.on.doc")
                                Text(copiedAlias ? "Скопировано!" : "Копировать номер \(walletNum)")
                            }
                            .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(copiedAlias ? .green : cyan)
                        .controlSize(.regular)
                    }

                    Button(action: {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(addr, forType: .string)
                        copiedFull = true
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { copiedFull = false }
                    }) {
                        HStack {
                            Image(systemName: copiedFull ? "checkmark" : "rectangle.on.rectangle")
                            Text(copiedFull ? "Скопировано!" : "Копировать полный адрес")
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .tint(copiedFull ? .green : .secondary)
                    .controlSize(.regular)
                }
            }
        }
        .padding()
        .frame(width: 280, height: walletNumValue > 0 ? 460 : 400)
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
