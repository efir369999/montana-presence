import UIKit

@main
class AppDelegate: UIResponder, UIApplicationDelegate {

    var window: UIWindow?

    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {

        window = UIWindow(frame: UIScreen.main.bounds)
        window?.rootViewController = ViewController()
        window?.makeKeyAndVisible()

        // Тёмный фон для launch screen
        window?.backgroundColor = UIColor(red: 15/255, green: 15/255, blue: 26/255, alpha: 1)

        return true
    }

    // Deep links (t.me/junomontanaagibot?start=...)
    func application(_ app: UIApplication, open url: URL, options: [UIApplication.OpenURLOptionsKey: Any] = [:]) -> Bool {
        if let vc = window?.rootViewController as? ViewController {
            // Передаём deep link в WebView
            let js = "window.handleDeepLink && window.handleDeepLink('\(url.absoluteString)')"
            vc.webView.evaluateJavaScript(js)
        }
        return true
    }
}
