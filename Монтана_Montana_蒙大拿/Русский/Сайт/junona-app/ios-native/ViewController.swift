import UIKit
import WebKit
import Contacts

class ViewController: UIViewController, WKNavigationDelegate, WKScriptMessageHandler {

    var webView: WKWebView!
    let serverURL = "http://72.56.102.240"

    override func viewDidLoad() {
        super.viewDidLoad()

        // Конфигурация WebView
        let config = WKWebViewConfiguration()
        let contentController = WKUserContentController()

        // JavaScript мост для нативных функций
        contentController.add(self, name: "montana")
        config.userContentController = contentController

        // Разрешаем inline media
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []

        // Создаём WebView
        webView = WKWebView(frame: view.bounds, configuration: config)
        webView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        webView.navigationDelegate = self
        webView.backgroundColor = UIColor(red: 15/255, green: 15/255, blue: 26/255, alpha: 1)
        webView.isOpaque = false
        webView.scrollView.bounces = false

        // Safe area
        if #available(iOS 11.0, *) {
            webView.scrollView.contentInsetAdjustmentBehavior = .never
        }

        view.addSubview(webView)

        // Загружаем сайт
        if let url = URL(string: serverURL) {
            webView.load(URLRequest(url: url))
        }
    }

    override var preferredStatusBarStyle: UIStatusBarStyle {
        return .lightContent
    }

    // MARK: - WKScriptMessageHandler

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: Any],
              let action = body["action"] as? String else { return }

        switch action {
        case "getContacts":
            requestContacts()
        case "haptic":
            let style = body["style"] as? String ?? "medium"
            triggerHaptic(style: style)
        default:
            break
        }
    }

    // MARK: - Native Functions

    func requestContacts() {
        let store = CNContactStore()

        store.requestAccess(for: .contacts) { granted, error in
            guard granted else {
                self.sendToJS("contactsResult", data: ["error": "Access denied"])
                return
            }

            let keys = [CNContactGivenNameKey, CNContactFamilyNameKey, CNContactPhoneNumbersKey] as [CNKeyDescriptor]
            let request = CNContactFetchRequest(keysToFetch: keys)

            var contacts: [[String: String]] = []

            do {
                try store.enumerateContacts(with: request) { contact, _ in
                    let name = "\(contact.givenName) \(contact.familyName)".trimmingCharacters(in: .whitespaces)
                    if let phone = contact.phoneNumbers.first?.value.stringValue {
                        contacts.append(["name": name, "phone": phone])
                    }
                }
                self.sendToJS("contactsResult", data: ["contacts": contacts])
            } catch {
                self.sendToJS("contactsResult", data: ["error": error.localizedDescription])
            }
        }
    }

    func triggerHaptic(style: String) {
        switch style {
        case "light":
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
        case "heavy":
            UIImpactFeedbackGenerator(style: .heavy).impactOccurred()
        case "success":
            UINotificationFeedbackGenerator().notificationOccurred(.success)
        case "error":
            UINotificationFeedbackGenerator().notificationOccurred(.error)
        default:
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        }
    }

    func sendToJS(_ event: String, data: [String: Any]) {
        if let jsonData = try? JSONSerialization.data(withJSONObject: data),
           let json = String(data: jsonData, encoding: .utf8) {
            DispatchQueue.main.async {
                self.webView.evaluateJavaScript("window.dispatchEvent(new CustomEvent('\(event)', {detail: \(json)}))")
            }
        }
    }

    // MARK: - WKNavigationDelegate

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if let url = navigationAction.request.url {
            // Открываем внешние ссылки в Safari
            if url.scheme == "tel" || url.scheme == "mailto" || url.host == "t.me" {
                UIApplication.shared.open(url)
                decisionHandler(.cancel)
                return
            }
        }
        decisionHandler(.allow)
    }
}
