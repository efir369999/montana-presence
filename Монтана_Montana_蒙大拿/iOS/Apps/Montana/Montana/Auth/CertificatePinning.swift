//
//  CertificatePinning.swift
//  Junona — Montana Messenger
//
//  Certificate Pinning для защиты от MITM атак
//  "Доверяй только своим серверам"
//

import Foundation
import CommonCrypto

// MARK: - Montana Network Security

/// Защищённый URLSession с Certificate Pinning
/// Предотвращает MITM атаки, проверяя SHA256 хеш публичного ключа сервера
final class MontanaNetworkSecurity: NSObject, URLSessionDelegate {

    static let shared = MontanaNetworkSecurity()

    // MARK: - Pinned Public Key Hashes

    /// SHA256 хеши публичных ключей серверов Montana
    /// Формат: base64(SHA256(SubjectPublicKeyInfo))
    ///
    /// Для получения хеша сертификата:
    /// ```bash
    /// openssl s_client -connect 1394793-cy33234.tw1.ru:443 </dev/null 2>/dev/null | \
    ///   openssl x509 -pubkey -noout | \
    ///   openssl pkey -pubin -outform DER | \
    ///   openssl dgst -sha256 -binary | base64
    /// ```
    private let pinnedHashes: Set<String> = [
        // Timeweb server (1394793-cy33234.tw1.ru)
        // TODO: Заменить на реальный хеш после получения сертификата
        "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=",

        // Amsterdam server (amsterdam.montana.network)
        // TODO: Заменить на реальный хеш
        "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC=",

        // Let's Encrypt Root CA (backup)
        "jQJTbIh0grw0/1TkHSumWb+Fs0Ggogr621gT3PvPKG0=",

        // Let's Encrypt E1 Intermediate
        "J2/oqMTsdhFWW/n85tys6b4yDBtb6idZayIEBx7QTxA="
    ]

    /// Домены, для которых применяется pinning
    private let pinnedDomains: Set<String> = [
        "1394793-cy33234.tw1.ru",
        "176.124.208.93",
        "amsterdam.montana.network",
        "72.56.102.240"
    ]

    // MARK: - Secure Session

    /// Защищённый URLSession с certificate pinning
    lazy var secureSession: URLSession = {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 60

        // Дополнительные настройки безопасности
        config.tlsMinimumSupportedProtocolVersion = .TLSv12
        config.httpShouldSetCookies = false

        return URLSession(
            configuration: config,
            delegate: self,
            delegateQueue: nil
        )
    }()

    private override init() {
        super.init()
    }

    // MARK: - URLSessionDelegate

    func urlSession(
        _ session: URLSession,
        didReceive challenge: URLAuthenticationChallenge,
        completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
    ) {
        // Проверяем только server trust challenges
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              let serverTrust = challenge.protectionSpace.serverTrust else {
            completionHandler(.performDefaultHandling, nil)
            return
        }

        let host = challenge.protectionSpace.host

        // Проверяем, нужен ли pinning для этого домена
        guard shouldPinForHost(host) else {
            // Для других доменов — стандартная проверка
            completionHandler(.performDefaultHandling, nil)
            return
        }

        // Проверяем certificate chain
        if validateCertificateChain(serverTrust: serverTrust, host: host) {
            let credential = URLCredential(trust: serverTrust)
            completionHandler(.useCredential, credential)
        } else {
            // Certificate pinning failed!
            print("[SECURITY] ⚠️ Certificate pinning FAILED for \(host)")
            print("[SECURITY] Possible MITM attack detected!")
            completionHandler(.cancelAuthenticationChallenge, nil)
        }
    }

    // MARK: - Pinning Logic

    private func shouldPinForHost(_ host: String) -> Bool {
        return pinnedDomains.contains(host)
    }

    private func validateCertificateChain(serverTrust: SecTrust, host: String) -> Bool {
        // Стандартная проверка системы
        var error: CFError?
        guard SecTrustEvaluateWithError(serverTrust, &error) else {
            print("[SECURITY] Trust evaluation failed: \(error?.localizedDescription ?? "unknown")")
            return false
        }

        // Проверяем публичный ключ каждого сертификата в цепочке
        let certificateCount = SecTrustGetCertificateCount(serverTrust)

        for index in 0..<certificateCount {
            guard let certificate = SecTrustGetCertificateAtIndex(serverTrust, index) else {
                continue
            }

            // Получаем публичный ключ
            guard let publicKey = SecCertificateCopyKey(certificate) else {
                continue
            }

            // Получаем данные публичного ключа
            var error: Unmanaged<CFError>?
            guard let publicKeyData = SecKeyCopyExternalRepresentation(publicKey, &error) as Data? else {
                continue
            }

            // Вычисляем SHA256 хеш
            let hash = sha256(publicKeyData)
            let hashBase64 = hash.base64EncodedString()

            // Проверяем против pinned hashes
            if pinnedHashes.contains(hashBase64) {
                print("[SECURITY] ✅ Certificate pinning PASSED for \(host)")
                return true
            }
        }

        return false
    }

    private func sha256(_ data: Data) -> Data {
        var hash = [UInt8](repeating: 0, count: Int(CC_SHA256_DIGEST_LENGTH))
        data.withUnsafeBytes {
            _ = CC_SHA256($0.baseAddress, CC_LONG(data.count), &hash)
        }
        return Data(hash)
    }
}

// MARK: - Convenience Extension

extension URLSession {
    /// Защищённая сессия Montana с certificate pinning
    static var montana: URLSession {
        return MontanaNetworkSecurity.shared.secureSession
    }
}

// MARK: - Debug Helper

#if DEBUG
extension MontanaNetworkSecurity {
    /// Выводит информацию о сертификате для добавления в pinned hashes
    func debugPrintCertificateInfo(for url: URL) {
        Task {
            var request = URLRequest(url: url)
            request.httpMethod = "HEAD"

            do {
                let (_, response) = try await URLSession.shared.data(for: request)
                if let httpResponse = response as? HTTPURLResponse {
                    print("[DEBUG] Response from \(url.host ?? "unknown"): \(httpResponse.statusCode)")
                    print("[DEBUG] To get certificate hash, run:")
                    print("openssl s_client -connect \(url.host ?? ""):\(url.port ?? 443) </dev/null 2>/dev/null | \\")
                    print("  openssl x509 -pubkey -noout | \\")
                    print("  openssl pkey -pubin -outform DER | \\")
                    print("  openssl dgst -sha256 -binary | base64")
                }
            } catch {
                print("[DEBUG] Error: \(error)")
            }
        }
    }
}
#endif
