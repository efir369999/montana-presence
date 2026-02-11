import SwiftUI
import Contacts

struct ContactsView: View {
    @EnvironmentObject var appState: AppState
    @State private var showImportSheet = false
    @State private var phoneContacts: [PhoneContact] = []
    @State private var selectedContacts: Set<String> = []
    @State private var isLoading = false
    @State private var searchText = ""

    var filteredContacts: [Contact] {
        if searchText.isEmpty {
            return appState.contacts
        }
        return appState.contacts.filter {
            $0.name.localizedCaseInsensitiveContains(searchText) ||
            $0.phone.contains(searchText)
        }
    }

    var body: some View {
        NavigationView {
            ZStack {
                Color("Background").ignoresSafeArea()

                if appState.contacts.isEmpty {
                    // Empty state
                    VStack(spacing: 20) {
                        Image(systemName: "person.2.fill")
                            .font(.system(size: 60))
                            .foregroundColor(.secondary)

                        Text("Нет контактов")
                            .font(.title2)
                            .foregroundColor(.secondary)

                        Button(action: { showImportSheet = true }) {
                            HStack {
                                Image(systemName: "plus.circle.fill")
                                Text("Импорт из телефона")
                            }
                            .padding()
                            .background(Color("Gold"))
                            .foregroundColor(Color("Background"))
                            .cornerRadius(12)
                        }
                    }
                } else {
                    // Contacts list
                    List {
                        ForEach(filteredContacts) { contact in
                            NavigationLink(destination: ConversationView(
                                contactPhone: contact.phone,
                                contactName: contact.name
                            )) {
                                ContactListRow(contact: contact)
                            }
                            .listRowBackground(Color("Card"))
                        }
                    }
                    .listStyle(.plain)
                    .searchable(text: $searchText, prompt: "Поиск")
                }
            }
            .navigationTitle("Контакты")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { showImportSheet = true }) {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showImportSheet) {
                ImportContactsView(onComplete: {
                    appState.loadContacts()
                })
            }
        }
    }
}

// MARK: - Contact List Row
struct ContactListRow: View {
    let contact: Contact

    var body: some View {
        HStack(spacing: 14) {
            // Avatar
            Text(String(contact.name.prefix(1)).uppercased())
                .font(.headline)
                .foregroundColor(Color("Background"))
                .frame(width: 48, height: 48)
                .background(
                    LinearGradient(
                        colors: [Color("Gold"), Color(hex: "FFA500")],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .clipShape(Circle())

            VStack(alignment: .leading, spacing: 2) {
                Text(contact.name)
                    .font(.body)
                    .foregroundColor(.white)
                Text(contact.phone)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            // Chat indicator
            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Import Contacts View
struct ImportContactsView: View {
    @Environment(\.dismiss) var dismiss
    @State private var phoneContacts: [PhoneContact] = []
    @State private var selectedIds: Set<String> = []
    @State private var isLoading = false
    @State private var error: String?
    @State private var contactsAccess = false

    let onComplete: () -> Void

    var body: some View {
        NavigationView {
            ZStack {
                Color("Background").ignoresSafeArea()

                if !contactsAccess {
                    // Request access
                    VStack(spacing: 20) {
                        Image(systemName: "person.crop.circle.badge.questionmark")
                            .font(.system(size: 60))
                            .foregroundColor(Color("Gold"))

                        Text("Доступ к контактам")
                            .font(.title2)

                        Text("Разреши доступ для импорта контактов")
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)

                        Button(action: requestAccess) {
                            Text("Разрешить")
                                .fontWeight(.semibold)
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color("Gold"))
                                .foregroundColor(Color("Background"))
                                .cornerRadius(12)
                        }
                        .padding(.horizontal, 40)
                    }
                } else if isLoading {
                    ProgressView("Загрузка...")
                } else if phoneContacts.isEmpty {
                    Text("Нет контактов для импорта")
                        .foregroundColor(.secondary)
                } else {
                    // Contacts list
                    VStack {
                        List {
                            ForEach(phoneContacts) { contact in
                                PhoneContactRow(
                                    contact: contact,
                                    isSelected: selectedIds.contains(contact.id)
                                ) {
                                    if selectedIds.contains(contact.id) {
                                        selectedIds.remove(contact.id)
                                    } else {
                                        selectedIds.insert(contact.id)
                                    }
                                }
                                .listRowBackground(Color("Card"))
                            }
                        }
                        .listStyle(.plain)

                        // Import button
                        Button(action: importSelected) {
                            Text("Импортировать (\(selectedIds.count))")
                                .fontWeight(.semibold)
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(selectedIds.isEmpty ? Color.gray : Color("Gold"))
                                .foregroundColor(Color("Background"))
                                .cornerRadius(12)
                        }
                        .disabled(selectedIds.isEmpty)
                        .padding()
                    }
                }

                if let error = error {
                    Text(error)
                        .foregroundColor(.red)
                }
            }
            .navigationTitle("Импорт контактов")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Отмена") { dismiss() }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Все") {
                        if selectedIds.count == phoneContacts.count {
                            selectedIds.removeAll()
                        } else {
                            selectedIds = Set(phoneContacts.map { $0.id })
                        }
                    }
                }
            }
            .onAppear {
                checkAccess()
            }
        }
    }

    private func checkAccess() {
        let status = CNContactStore.authorizationStatus(for: .contacts)
        if status == .authorized {
            contactsAccess = true
            loadContacts()
        }
    }

    private func requestAccess() {
        let store = CNContactStore()
        store.requestAccess(for: .contacts) { granted, error in
            DispatchQueue.main.async {
                contactsAccess = granted
                if granted {
                    loadContacts()
                } else {
                    self.error = "Доступ запрещён. Разреши в Настройках."
                }
            }
        }
    }

    private func loadContacts() {
        isLoading = true
        let store = CNContactStore()
        let keys = [CNContactGivenNameKey, CNContactFamilyNameKey, CNContactPhoneNumbersKey] as [CNKeyDescriptor]

        DispatchQueue.global(qos: .userInitiated).async {
            do {
                var contacts: [PhoneContact] = []
                let request = CNContactFetchRequest(keysToFetch: keys)

                try store.enumerateContacts(with: request) { contact, _ in
                    let name = "\(contact.givenName) \(contact.familyName)".trimmingCharacters(in: .whitespaces)
                    for phone in contact.phoneNumbers {
                        let number = phone.value.stringValue
                        contacts.append(PhoneContact(
                            id: contact.identifier + number,
                            name: name.isEmpty ? "Без имени" : name,
                            phone: number
                        ))
                    }
                }

                DispatchQueue.main.async {
                    self.phoneContacts = contacts.sorted { $0.name < $1.name }
                    self.isLoading = false
                }
            } catch {
                DispatchQueue.main.async {
                    self.error = "Ошибка загрузки контактов"
                    self.isLoading = false
                }
            }
        }
    }

    private func importSelected() {
        guard let telegramId = UserDefaults.standard.string(forKey: "telegramId") ??
              UserDefaults.standard.string(forKey: "deviceId") else {
            error = "Не авторизован"
            return
        }

        isLoading = true
        let selected = phoneContacts.filter { selectedIds.contains($0.id) }
        let group = DispatchGroup()

        for contact in selected {
            group.enter()
            API.shared.saveContact(telegramId: telegramId, name: contact.name, phone: contact.phone) { _ in
                group.leave()
            }
        }

        group.notify(queue: .main) {
            isLoading = false
            onComplete()
            dismiss()
        }
    }
}

// MARK: - Phone Contact Row
struct PhoneContactRow: View {
    let contact: PhoneContact
    let isSelected: Bool
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 14) {
                // Checkbox
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .foregroundColor(isSelected ? Color("Gold") : .secondary)
                    .font(.title2)

                // Avatar
                Text(String(contact.name.prefix(1)).uppercased())
                    .font(.headline)
                    .foregroundColor(Color("Background"))
                    .frame(width: 44, height: 44)
                    .background(Color("Gold").opacity(0.8))
                    .clipShape(Circle())

                VStack(alignment: .leading, spacing: 2) {
                    Text(contact.name)
                        .foregroundColor(.white)
                    Text(contact.phone)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Spacer()
            }
            .padding(.vertical, 4)
        }
    }
}
