import SwiftUI

struct ContentView: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        Group {
            if appState.isLoggedIn {
                MainTabView()
            } else {
                LoginView()
            }
        }
        .animation(.easeInOut, value: appState.isLoggedIn)
    }
}

// MARK: - Main Tab View
struct MainTabView: View {
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            ChatsView()
                .tabItem {
                    Image(systemName: "bubble.left.and.bubble.right.fill")
                    Text("Чаты")
                }
                .tag(0)

            ContactsView()
                .tabItem {
                    Image(systemName: "person.2.fill")
                    Text("Контакты")
                }
                .tag(1)

            WalletView()
                .tabItem {
                    Image(systemName: "creditcard.fill")
                    Text("Кошелёк")
                }
                .tag(2)

            ChatView()
                .tabItem {
                    Image(systemName: "sun.max.fill")
                    Text("Юнона")
                }
                .tag(3)

            SettingsView()
                .tabItem {
                    Image(systemName: "gearshape.fill")
                    Text("Ещё")
                }
                .tag(4)
        }
        .accentColor(Color("Gold"))
    }
}

// MARK: - Preview
struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
            .environmentObject(AppState())
    }
}
