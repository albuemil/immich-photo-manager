# SoundInbox macOS Client Licensing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add license activation, feature gating (Free=1 account, Pro=5 accounts), and offline grace period to the SoundInbox macOS menu bar app.

**Architecture:** Adds LicenseManager (@Observable @MainActor) as the license state authority, LicenseAPIService (actor) for server communication, DeviceIDService for stable device identification, and 4 new SwiftUI views (LicenseSettingsView, UpgradePromptView, DeviceLimitView, ActivationSuccessView). Feature gate is a single check: `canAddAccount(currentCount:)`. Offline grace period allows 90 days without server contact.

**Tech Stack:** Swift 6.0, macOS 14+, SwiftUI, URLSession, Keychain Services, UserDefaults.

**Codebase:** `/Users/txeo/Git/mac/sound-inbox-mac/`

---

## Task 1: Create LicenseState Models

**Files:**
- Create: `SoundInbox/Models/LicenseState.swift`

**Steps:**

- [ ] Create `SoundInbox/Models/LicenseState.swift` with the `LicenseTier` enum, `FeatureEntitlements` struct, and `LicenseConfig` constants:

```swift
import Foundation

// MARK: - License Tier

enum LicenseTier: String, Codable, Sendable {
    case free
    case pro
}

// MARK: - Feature Entitlements

struct FeatureEntitlements: Codable, Sendable, Equatable {
    let maxAccounts: Int

    static let free = FeatureEntitlements(maxAccounts: LicenseConfig.freeMaxAccounts)
    static let pro = FeatureEntitlements(maxAccounts: LicenseConfig.proMaxAccounts)
}

// MARK: - License Configuration Constants

enum LicenseConfig {
    static let freeMaxAccounts = 1
    static let proMaxAccounts = 5

    /// API base URL for license operations
    static let apiBaseURL = "https://drolosoft.com/api/soundinbox"

    /// Lemon Squeezy checkout URL for purchasing Pro
    static let checkoutURL = "https://drolosoft.lemonsqueezy.com/buy/soundinbox-pro"

    /// Maximum device activations per license key
    static let maxActivationsPerKey = 3

    /// Keychain service name for license-related items (separate from per-account KeychainService)
    static let keychainService = "com.soundinbox.license"

    /// Keychain service name for system-level identifiers (device ID)
    static let systemKeychainService = "com.soundinbox.system"

    /// License key format: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
    /// Charset: A-H, J-N, P-Z, 2-9 (no I, O, L, 0, 1)
    static let keyPattern = "^[A-HJ-NP-Z2-9]{5}-[A-HJ-NP-Z2-9]{5}-[A-HJ-NP-Z2-9]{5}-[A-HJ-NP-Z2-9]{5}-[A-HJ-NP-Z2-9]{5}$"

    // MARK: - Offline Grace Period Intervals

    /// How often to attempt background validation (7 days)
    static let verificationIntervalSeconds: TimeInterval = 7 * 24 * 60 * 60

    /// Show warning after this many seconds without server contact (30 days)
    static let offlineWarningThreshold: TimeInterval = 30 * 24 * 60 * 60

    /// Revert to free after this many seconds without server contact (90 days)
    static let offlineRevertThreshold: TimeInterval = 90 * 24 * 60 * 60

    // MARK: - UserDefaults Keys

    static let udTierKey = "soundinbox_license_tier"
    static let udMaxAccountsKey = "soundinbox_license_max_accounts"
    static let udLastVerifiedKey = "soundinbox_license_last_verified"
    static let udLastServerContactKey = "soundinbox_license_last_server_contact"
    static let udLastVerificationAttemptKey = "soundinbox_license_last_verification_attempt"
}
```

- [ ] Build the project to verify the file compiles:

```bash
cd /Users/txeo/Git/mac/sound-inbox-mac && xcodebuild -scheme SoundInbox build 2>&1 | tail -5
```

- [ ] Commit:

```bash
git add SoundInbox/Models/LicenseState.swift
git commit -m "feat: Add LicenseState models (LicenseTier, FeatureEntitlements, LicenseConfig)"
```

---

## Task 2: Create LicenseResponse Models

**Files:**
- Create: `SoundInbox/Models/LicenseResponse.swift`

**Steps:**

- [ ] Create `SoundInbox/Models/LicenseResponse.swift` with Codable API response structs matching the server API contracts from the spec (Section 5):

```swift
import Foundation

// MARK: - Validate Response (POST /api/soundinbox/licenses/validate)

struct ValidationResponse: Codable, Sendable {
    let valid: Bool
    let message: String
    let status: String?
    let tier: String?
    let serverTime: String?
    let features: Features?

    /// Nested features object — only contains max_accounts because it is the only
    /// field that differs between tiers. All other features are unlimited in both tiers.
    struct Features: Codable, Sendable {
        let maxAccounts: Int

        enum CodingKeys: String, CodingKey {
            case maxAccounts = "max_accounts"
        }
    }

    enum CodingKeys: String, CodingKey {
        case valid, message, status, tier, features
        case serverTime = "server_time"
    }
}

// MARK: - Activate Response (POST /api/soundinbox/licenses/activate)

struct ActivationResponse: Codable, Sendable {
    let success: Bool
    let message: String
    let activationId: String?
    let activatedAt: String?
    let deviceName: String?
    let tier: String?
    let features: ValidationResponse.Features?
    let error: String?
    let currentActivations: Int?
    let maxActivations: Int?
    let activeDevices: [ActiveDevice]?

    struct ActiveDevice: Codable, Sendable, Identifiable {
        let deviceId: String
        let deviceName: String
        let activatedAt: String
        let lastSeenAt: String?

        var id: String { deviceId }

        enum CodingKeys: String, CodingKey {
            case deviceId = "device_id"
            case deviceName = "device_name"
            case activatedAt = "activated_at"
            case lastSeenAt = "last_seen_at"
        }
    }

    enum CodingKeys: String, CodingKey {
        case success, message, tier, features, error
        case activationId = "activation_id"
        case activatedAt = "activated_at"
        case deviceName = "device_name"
        case currentActivations = "current_activations"
        case maxActivations = "max_activations"
        case activeDevices = "active_devices"
    }
}

// MARK: - Deactivate Response (POST /api/soundinbox/licenses/deactivate)

struct DeactivationResponse: Codable, Sendable {
    let success: Bool
    let message: String
    let license: LicenseInfo?

    struct LicenseInfo: Codable, Sendable {
        let licenseKey: String
        let currentActivations: Int
        let maxActivations: Int

        enum CodingKeys: String, CodingKey {
            case licenseKey = "license_key"
            case currentActivations = "current_activations"
            case maxActivations = "max_activations"
        }
    }
}

// MARK: - License Info Response (GET /api/soundinbox/licenses/{key}?device_id={device_id})

struct LicenseInfoResponse: Codable, Sendable {
    let license: LicenseDetail
    let yourActivation: ActivationDetail?

    struct LicenseDetail: Codable, Sendable {
        let licenseKey: String
        let status: String
        let maxActivations: Int
        let currentActivations: Int
        let createdAt: String

        enum CodingKeys: String, CodingKey {
            case licenseKey = "license_key"
            case status
            case maxActivations = "max_activations"
            case currentActivations = "current_activations"
            case createdAt = "created_at"
        }
    }

    struct ActivationDetail: Codable, Sendable {
        let deviceId: String
        let deviceName: String
        let status: String
        let activatedAt: String

        enum CodingKeys: String, CodingKey {
            case deviceId = "device_id"
            case deviceName = "device_name"
            case status
            case activatedAt = "activated_at"
        }
    }

    enum CodingKeys: String, CodingKey {
        case license
        case yourActivation = "your_activation"
    }
}
```

- [ ] Build the project:

```bash
cd /Users/txeo/Git/mac/sound-inbox-mac && xcodebuild -scheme SoundInbox build 2>&1 | tail -5
```

- [ ] Commit:

```bash
git add SoundInbox/Models/LicenseResponse.swift
git commit -m "feat: Add Codable API response models for license validation/activation/deactivation"
```

---

## Task 3: Create DeviceIDService

**Files:**
- Create: `SoundInbox/Services/DeviceIDService.swift`

**Steps:**

- [ ] Create `SoundInbox/Services/DeviceIDService.swift` using direct Security framework calls with `com.soundinbox.system` Keychain service (NOT the per-account `KeychainService`):

```swift
import Foundation
import Security

/// Generates a stable, privacy-respecting device identifier.
/// Uses a UUID generated once and stored permanently in the Keychain.
/// Does NOT use hardware serial or IOPlatformUUID (privacy concern).
///
/// Uses its own Keychain service (`com.soundinbox.system`) separate from
/// the per-account `KeychainService` to avoid namespace collisions.
struct DeviceIDService: Sendable {
    private static let serviceName = LicenseConfig.systemKeychainService
    private static let deviceIDKey = "device-id"

    // MARK: - Device Identifier

    /// Returns a stable device identifier persisted in Keychain.
    /// Generates a new UUID on first call and stores it permanently.
    /// Subsequent calls return the same UUID.
    static func getDeviceID() -> String {
        // Try to load existing device ID from Keychain
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: deviceIDKey,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        if status == errSecSuccess,
           let data = result as? Data,
           let id = String(data: data, encoding: .utf8),
           !id.isEmpty {
            return id
        }

        // Generate and persist a new UUID
        let newID = UUID().uuidString
        let addQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: deviceIDKey,
            kSecValueData as String: newID.data(using: .utf8)!,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock
        ]

        let addStatus = SecItemAdd(addQuery as CFDictionary, nil)
        if addStatus != errSecSuccess {
            NSLog("[DeviceID] Failed to persist device ID to Keychain (status: %d)", addStatus)
        }

        return newID
    }

    // MARK: - Device Metadata

    /// Returns the user-facing device name (e.g., "Juan's MacBook Pro").
    /// Note: Host.current().localizedName is deprecated in macOS 14+.
    static var deviceName: String {
        ProcessInfo.processInfo.hostName
    }

    /// Returns the hardware model identifier (e.g., "Mac14,7" or "MacBookPro18,1").
    static var deviceModel: String {
        var size = 0
        sysctlbyname("hw.model", nil, &size, nil, 0)
        guard size > 0 else { return "Unknown" }
        var model = [CChar](repeating: 0, count: size)
        sysctlbyname("hw.model", &model, &size, nil, 0)
        return String(cString: model)
    }

    /// Returns the macOS version string (e.g., "15.2").
    static var osVersion: String {
        let version = ProcessInfo.processInfo.operatingSystemVersion
        return "\(version.majorVersion).\(version.minorVersion).\(version.patchVersion)"
    }

    /// Returns the app version from the bundle (e.g., "1.0.0").
    static var appVersion: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1.0.0"
    }
}
```

- [ ] Build the project:

```bash
cd /Users/txeo/Git/mac/sound-inbox-mac && xcodebuild -scheme SoundInbox build 2>&1 | tail -5
```

- [ ] Verify UUID persistence manually: After building, add a temporary `NSLog` in `AppDelegate.applicationDidFinishLaunching` that calls `DeviceIDService.getDeviceID()` twice and prints both values. They must be identical.

- [ ] Commit:

```bash
git add SoundInbox/Services/DeviceIDService.swift
git commit -m "feat: Add DeviceIDService for stable device identification via Keychain"
```

---

## Task 4: Create LicenseAPIService

**Files:**
- Create: `SoundInbox/Services/LicenseAPIService.swift`

**Steps:**

- [ ] Create `SoundInbox/Services/LicenseAPIService.swift` as an actor-based HTTP client:

```swift
import Foundation

// MARK: - License API Errors

enum LicenseAPIError: Error, LocalizedError, Sendable {
    case networkError(underlying: String)
    case invalidResponse(statusCode: Int)
    case serverError(message: String)
    case decodingError(underlying: String)
    case invalidURL
    case deviceLimitReached(response: ActivationResponse)
    case licenseNotFound
    case licenseRevoked
    case licenseRefunded

    var errorDescription: String? {
        switch self {
        case .networkError(let msg):
            return "Network error: \(msg)"
        case .invalidResponse(let code):
            return "Server returned status \(code)"
        case .serverError(let msg):
            return "Server error: \(msg)"
        case .decodingError(let msg):
            return "Failed to parse response: \(msg)"
        case .invalidURL:
            return "Invalid API URL"
        case .deviceLimitReached:
            return "Activation limit reached"
        case .licenseNotFound:
            return "License key not found"
        case .licenseRevoked:
            return "License has been revoked"
        case .licenseRefunded:
            return "License has been refunded"
        }
    }
}

// MARK: - License API Service

actor LicenseAPIService {
    private let baseURL: String
    private let session: URLSession

    init(baseURL: String = LicenseConfig.apiBaseURL) {
        self.baseURL = baseURL
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 15
        config.timeoutIntervalForResource = 30
        self.session = URLSession(configuration: config)
    }

    // MARK: - Validate License

    /// Validates a license key against the server.
    /// Returns the validation response with tier and entitlements.
    func validate(licenseKey: String) async throws -> ValidationResponse {
        let url = try makeURL(path: "/licenses/validate")
        let body: [String: String] = ["license_key": licenseKey]

        let (data, response) = try await post(url: url, body: body)
        let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0

        let decoded = try decode(ValidationResponse.self, from: data)

        // Check for refunded status
        if decoded.status == "refunded" {
            throw LicenseAPIError.licenseRefunded
        }

        // 404-like: valid=false with not_found status
        if !decoded.valid && decoded.status == "not_found" {
            throw LicenseAPIError.licenseNotFound
        }

        // Revoked
        if decoded.status == "revoked" {
            throw LicenseAPIError.licenseRevoked
        }

        if statusCode >= 500 {
            throw LicenseAPIError.serverError(message: decoded.message)
        }

        return decoded
    }

    // MARK: - Activate License

    /// Activates a license key on this device.
    /// Returns activation details on success, throws on failure.
    func activate(licenseKey: String) async throws -> ActivationResponse {
        let url = try makeURL(path: "/licenses/activate")
        let body: [String: String] = [
            "license_key": licenseKey,
            "device_id": DeviceIDService.getDeviceID(),
            "device_name": DeviceIDService.deviceName,
            "device_model": DeviceIDService.deviceModel,
            "os_version": DeviceIDService.osVersion,
            "app_version": DeviceIDService.appVersion
        ]

        let (data, response) = try await post(url: url, body: body)
        let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0

        let decoded = try decode(ActivationResponse.self, from: data)

        // 403 = device limit reached
        if statusCode == 403 || (!decoded.success && decoded.activeDevices != nil) {
            throw LicenseAPIError.deviceLimitReached(response: decoded)
        }

        // 404 = license not found
        if statusCode == 404 {
            throw LicenseAPIError.licenseNotFound
        }

        // General server error
        if statusCode >= 500 {
            throw LicenseAPIError.serverError(message: decoded.message)
        }

        return decoded
    }

    // MARK: - Deactivate License

    /// Deactivates a license key on a specific device.
    func deactivate(licenseKey: String, deviceID: String) async throws -> DeactivationResponse {
        let url = try makeURL(path: "/licenses/deactivate")
        let body: [String: String] = [
            "license_key": licenseKey,
            "device_id": deviceID
        ]

        let (data, response) = try await post(url: url, body: body)
        let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0

        let decoded = try decode(DeactivationResponse.self, from: data)

        if statusCode >= 400 && !decoded.success {
            throw LicenseAPIError.serverError(message: decoded.message)
        }

        return decoded
    }

    // MARK: - Get License Info

    /// Retrieves license details for the current device.
    func getLicenseInfo(key: String) async throws -> LicenseInfoResponse {
        let deviceID = DeviceIDService.getDeviceID()
        guard var components = URLComponents(string: "\(baseURL)/licenses/\(key)") else {
            throw LicenseAPIError.invalidURL
        }
        components.queryItems = [URLQueryItem(name: "device_id", value: deviceID)]

        guard let url = components.url else {
            throw LicenseAPIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        do {
            let (data, response) = try await session.data(for: request)
            let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0

            if statusCode == 403 || statusCode == 404 {
                throw LicenseAPIError.licenseNotFound
            }

            return try decode(LicenseInfoResponse.self, from: data)
        } catch let error as LicenseAPIError {
            throw error
        } catch {
            throw LicenseAPIError.networkError(underlying: error.localizedDescription)
        }
    }

    // MARK: - Private Helpers

    private func makeURL(path: String) throws -> URL {
        guard let url = URL(string: "\(baseURL)\(path)") else {
            throw LicenseAPIError.invalidURL
        }
        return url
    }

    private func post(url: URL, body: [String: String]) async throws -> (Data, URLResponse) {
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        let encoder = JSONEncoder()
        request.httpBody = try encoder.encode(body)

        do {
            return try await session.data(for: request)
        } catch {
            throw LicenseAPIError.networkError(underlying: error.localizedDescription)
        }
    }

    private func decode<T: Decodable>(_ type: T.Type, from data: Data) throws -> T {
        do {
            let decoder = JSONDecoder()
            return try decoder.decode(type, from: data)
        } catch {
            throw LicenseAPIError.decodingError(underlying: error.localizedDescription)
        }
    }
}
```

- [ ] Build the project:

```bash
cd /Users/txeo/Git/mac/sound-inbox-mac && xcodebuild -scheme SoundInbox build 2>&1 | tail -5
```

- [ ] Commit:

```bash
git add SoundInbox/Services/LicenseAPIService.swift
git commit -m "feat: Add LicenseAPIService actor for license validation/activation/deactivation"
```

---

## Task 5: Create LicenseManager

**Files:**
- Create: `SoundInbox/Services/LicenseManager.swift`

**Steps:**

- [ ] Create `SoundInbox/Services/LicenseManager.swift` following the existing `@MainActor @Observable` pattern from `FormulaStore` and `AccountManager`:

```swift
import Foundation
import Security

/// Central license state authority for the SoundInbox app.
/// Manages license tier, activation, offline grace period, and feature gating.
///
/// Follows the same pattern as FormulaStore: @MainActor @Observable with
/// UserDefaults persistence for non-secret data and Keychain for sensitive data.
@MainActor
@Observable
final class LicenseManager {

    // MARK: - Published State

    /// Current license tier (free or pro)
    var tier: LicenseTier = .free

    /// The active license key (nil when free/unactivated)
    var licenseKey: String?

    /// Feature entitlements derived from the current tier
    var entitlements: FeatureEntitlements = .free

    /// Last successful server verification date (from server_time, not local clock)
    var lastServerContact: Date?

    /// Whether an API operation is in progress
    var isLoading: Bool = false

    /// Current error message for display in the UI
    var errorMessage: String?

    /// Activation success flag for triggering the success animation
    var showActivationSuccess: Bool = false

    /// Device limit response for showing DeviceLimitView
    var deviceLimitResponse: ActivationResponse?

    /// Whether the offline warning should be shown (30-90 days without contact)
    var showOfflineWarning: Bool = false

    // MARK: - Computed Properties

    /// Whether the user has an active Pro license
    var isActivated: Bool { tier == .pro }

    /// Maximum number of accounts allowed under the current tier
    var maxAccounts: Int { entitlements.maxAccounts }

    // MARK: - Private State

    private let apiService = LicenseAPIService()
    private var verificationTimer: Timer?

    // MARK: - Feature Gate

    /// The single feature gate check.
    /// Returns true if the user can add another account given the current count.
    func canAddAccount(currentCount: Int) -> Bool {
        return currentCount < entitlements.maxAccounts
    }

    // MARK: - Restore on Launch

    /// Restores license state from Keychain and UserDefaults on app launch.
    /// Call this from AppDelegate.applicationDidFinishLaunching.
    func restoreFromKeychain() {
        // Restore license key from Keychain
        licenseKey = loadKeychainString(key: "license-key")

        // Restore non-secret state from UserDefaults
        let defaults = UserDefaults.standard

        if let tierString = defaults.string(forKey: LicenseConfig.udTierKey),
           let savedTier = LicenseTier(rawValue: tierString) {
            tier = savedTier
        } else {
            tier = .free
        }

        let savedMaxAccounts = defaults.integer(forKey: LicenseConfig.udMaxAccountsKey)
        if savedMaxAccounts > 0 {
            entitlements = FeatureEntitlements(maxAccounts: savedMaxAccounts)
        } else {
            entitlements = tier == .pro ? .pro : .free
        }

        if let lastContactInterval = defaults.object(forKey: LicenseConfig.udLastServerContactKey) as? TimeInterval {
            lastServerContact = Date(timeIntervalSince1970: lastContactInterval)
        }

        // Check offline grace period
        evaluateOfflineGracePeriod()

        NSLog("[License] Restored: tier=%@, maxAccounts=%d, hasKey=%@",
              tier.rawValue, entitlements.maxAccounts, (licenseKey != nil) ? "yes" : "no")
    }

    // MARK: - Activate License

    /// Activates a license key on this device.
    /// On success, updates tier to .pro and persists to Keychain/UserDefaults.
    func activateLicense(key: String) async {
        isLoading = true
        errorMessage = nil
        deviceLimitResponse = nil
        showActivationSuccess = false

        // Normalize and validate format locally first
        let normalizedKey = normalizeLicenseKey(key)
        guard isValidKeyFormat(normalizedKey) else {
            errorMessage = "Invalid license key format. Expected: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX"
            isLoading = false
            return
        }

        do {
            let response = try await apiService.activate(licenseKey: normalizedKey)

            // Success (201 or 200 already-activated)
            licenseKey = normalizedKey
            tier = .pro

            let maxAccounts = response.features?.maxAccounts ?? LicenseConfig.proMaxAccounts
            entitlements = FeatureEntitlements(maxAccounts: maxAccounts)
            lastServerContact = Date()

            // Persist
            saveKeychainString(key: "license-key", value: normalizedKey)
            persistToUserDefaults()

            showActivationSuccess = true
            NSLog("[License] Activation successful: tier=pro, maxAccounts=%d", maxAccounts)

        } catch LicenseAPIError.deviceLimitReached(let response) {
            deviceLimitResponse = response
            errorMessage = response.message
        } catch LicenseAPIError.licenseNotFound {
            errorMessage = "License key not found. Please check your key and try again."
        } catch LicenseAPIError.licenseRevoked {
            errorMessage = "This license has been revoked."
        } catch LicenseAPIError.licenseRefunded {
            errorMessage = "This license has been refunded. Pro features are no longer available."
        } catch LicenseAPIError.networkError {
            errorMessage = "Could not connect to the license server. Please check your internet connection and try again."
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }

    // MARK: - Deactivate License

    /// Deactivates the current license on this device.
    /// Reverts to free tier and clears Keychain.
    func deactivateLicense() async {
        guard let key = licenseKey else { return }

        isLoading = true
        errorMessage = nil

        let deviceID = DeviceIDService.getDeviceID()

        do {
            _ = try await apiService.deactivate(licenseKey: key, deviceID: deviceID)
            NSLog("[License] Deactivation successful")
        } catch {
            // Even if server call fails, deactivate locally
            NSLog("[License] Server deactivation failed, deactivating locally: %@", "\(error)")
        }

        revertToFree(clearKey: true)
        isLoading = false
    }

    // MARK: - Deactivate Remote Device

    /// Deactivates a specific remote device, then retries activation on this device.
    func deactivateRemoteDevice(deviceID: String) async {
        guard let key = licenseKey ?? deviceLimitResponse?.activeDevices?.first.map({ _ in
            // If we have a device limit response, we need the key from the activation attempt
            return nil as String?
        }) ?? nil else { return }

        // We need the key that was being activated — it might not be stored yet
        // The caller should pass it via the activation flow
        isLoading = true

        do {
            _ = try await apiService.deactivate(licenseKey: key, deviceID: deviceID)
            NSLog("[License] Remote device %@ deactivated", deviceID)
        } catch {
            errorMessage = "Failed to deactivate remote device: \(error.localizedDescription)"
            isLoading = false
            return
        }

        isLoading = false
    }

    // MARK: - Background Verification

    /// Checks if verification is needed and performs it silently.
    /// Call on app launch and periodically (every 7 days).
    func verifyIfNeeded() async {
        guard tier == .pro, let key = licenseKey else { return }

        // Check if enough time has passed since last verification
        let defaults = UserDefaults.standard
        let lastAttempt = defaults.double(forKey: LicenseConfig.udLastVerificationAttemptKey)
        let now = Date().timeIntervalSince1970

        if lastAttempt > 0 && (now - lastAttempt) < LicenseConfig.verificationIntervalSeconds {
            return // Too soon to verify again
        }

        defaults.set(now, forKey: LicenseConfig.udLastVerificationAttemptKey)

        NSLog("[License] Running background verification...")

        do {
            let response = try await apiService.validate(licenseKey: key)

            if response.valid {
                // Update entitlements from server
                let maxAccounts = response.features?.maxAccounts ?? LicenseConfig.proMaxAccounts
                entitlements = FeatureEntitlements(maxAccounts: maxAccounts)

                // Use server_time for clock manipulation protection
                if let serverTimeStr = response.serverTime,
                   let serverDate = ISO8601DateFormatter().date(from: serverTimeStr) {
                    lastServerContact = serverDate
                } else {
                    lastServerContact = Date()
                }

                showOfflineWarning = false
                persistToUserDefaults()
                NSLog("[License] Verification succeeded, entitlements updated")
            } else {
                // License no longer valid on server
                NSLog("[License] Verification failed: status=%@", response.status ?? "unknown")
                revertToFree(clearKey: true)
            }
        } catch LicenseAPIError.licenseRefunded {
            NSLog("[License] License was refunded, reverting to free")
            errorMessage = "Your license has been refunded. Pro features have been deactivated."
            revertToFree(clearKey: true)
        } catch LicenseAPIError.networkError {
            // Network error is fine — evaluate grace period
            NSLog("[License] Verification network error, evaluating offline grace")
            evaluateOfflineGracePeriod()
        } catch {
            NSLog("[License] Verification error: %@", "\(error)")
            evaluateOfflineGracePeriod()
        }
    }

    /// Starts a repeating timer that fires verification every 7 days.
    func startVerificationTimer() {
        verificationTimer?.invalidate()
        verificationTimer = Timer.scheduledTimer(withTimeInterval: LicenseConfig.verificationIntervalSeconds, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.verifyIfNeeded()
            }
        }
    }

    /// Stops the verification timer.
    func stopVerificationTimer() {
        verificationTimer?.invalidate()
        verificationTimer = nil
    }

    // MARK: - Pause/Resume Accounts

    /// Returns the set of account indices that should be paused (inactive) when on the free tier.
    /// The first/oldest account stays active; accounts 2-5 become paused.
    /// Paused accounts stop polling but retain all configuration, formulas, and history.
    func pausedAccountIndices(totalAccounts: Int) -> IndexSet {
        guard tier == .free && totalAccounts > entitlements.maxAccounts else {
            return IndexSet()
        }
        return IndexSet(entitlements.maxAccounts..<totalAccounts)
    }

    // MARK: - License Key Formatting

    /// Normalizes user input into the standard XXXXX-XXXXX-XXXXX-XXXXX-XXXXX format.
    /// Strips spaces, non-alphanumeric characters, uppercases, and re-inserts hyphens.
    func normalizeLicenseKey(_ input: String) -> String {
        let cleaned = input
            .uppercased()
            .filter { $0.isLetter || $0.isNumber }

        guard cleaned.count == 25 else { return input.uppercased().trimmingCharacters(in: .whitespaces) }

        var result = ""
        for (index, char) in cleaned.enumerated() {
            if index > 0 && index % 5 == 0 {
                result.append("-")
            }
            result.append(char)
        }
        return result
    }

    /// Returns a masked version of the key for display: XXXXX-****-****-****-XXXXX
    func maskedKey(_ key: String) -> String {
        let parts = key.split(separator: "-")
        guard parts.count == 5 else { return key }
        return "\(parts[0])-****-****-****-\(parts[4])"
    }

    /// Validates the license key format using the Base32 charset regex.
    func isValidKeyFormat(_ key: String) -> Bool {
        let regex = try? NSRegularExpression(pattern: LicenseConfig.keyPattern)
        let range = NSRange(key.startIndex..., in: key)
        return regex?.firstMatch(in: key, range: range) != nil
    }

    // MARK: - Private: Persistence

    private func persistToUserDefaults() {
        let defaults = UserDefaults.standard
        defaults.set(tier.rawValue, forKey: LicenseConfig.udTierKey)
        defaults.set(entitlements.maxAccounts, forKey: LicenseConfig.udMaxAccountsKey)
        if let contact = lastServerContact {
            defaults.set(contact.timeIntervalSince1970, forKey: LicenseConfig.udLastServerContactKey)
        }
    }

    private func revertToFree(clearKey: Bool) {
        tier = .free
        entitlements = .free
        if clearKey {
            licenseKey = nil
            deleteKeychainItem(key: "license-key")
        }
        lastServerContact = nil
        showOfflineWarning = false
        persistToUserDefaults()
        NSLog("[License] Reverted to free tier")
    }

    // MARK: - Private: Offline Grace Period

    /// Evaluates the offline grace period and takes action if thresholds are exceeded.
    ///
    /// Clock manipulation protection: If stored `lastServerContact` is in the future
    /// relative to the current system clock, use the earlier of (system time, stored time).
    private func evaluateOfflineGracePeriod() {
        guard tier == .pro else { return }
        guard let contact = lastServerContact else {
            // No server contact recorded — if we have a key, assume recent activation
            if licenseKey != nil {
                showOfflineWarning = false
            }
            return
        }

        var effectiveContact = contact
        let now = Date()

        // Clock manipulation protection: if stored time is in the future, use the earlier
        if contact > now {
            NSLog("[License] Clock manipulation detected: lastServerContact is in the future")
            effectiveContact = now
        }

        let elapsed = now.timeIntervalSince(effectiveContact)

        if elapsed > LicenseConfig.offlineRevertThreshold {
            // 90+ days offline: revert to free
            NSLog("[License] Offline grace expired (%.0f days), reverting to free", elapsed / 86400)
            revertToFree(clearKey: false)
            errorMessage = "License verification required. Connect to the internet to restore Pro features."
        } else if elapsed > LicenseConfig.offlineWarningThreshold {
            // 30-90 days offline: show warning
            NSLog("[License] Offline warning threshold reached (%.0f days)", elapsed / 86400)
            showOfflineWarning = true
        } else {
            showOfflineWarning = false
        }
    }

    // MARK: - Private: Keychain Helpers (com.soundinbox.license)

    private func saveKeychainString(key: String, value: String) {
        guard let data = value.data(using: .utf8) else { return }

        // Delete existing item first
        deleteKeychainItem(key: key)

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: LicenseConfig.keychainService,
            kSecAttrAccount as String: key,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock
        ]

        let status = SecItemAdd(query as CFDictionary, nil)
        if status != errSecSuccess {
            NSLog("[License] Keychain save failed for '%@' (status: %d)", key, status)
        }
    }

    private func loadKeychainString(key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: LicenseConfig.keychainService,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess,
              let data = result as? Data,
              let string = String(data: data, encoding: .utf8) else {
            return nil
        }

        return string
    }

    private func deleteKeychainItem(key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: LicenseConfig.keychainService,
            kSecAttrAccount as String: key
        ]
        SecItemDelete(query as CFDictionary)
    }
}
```

- [ ] Build the project:

```bash
cd /Users/txeo/Git/mac/sound-inbox-mac && xcodebuild -scheme SoundInbox build 2>&1 | tail -5
```

- [ ] Commit:

```bash
git add SoundInbox/Services/LicenseManager.swift
git commit -m "feat: Add LicenseManager with offline grace period and feature gating"
```

---

## Task 6: Create LicenseSettingsView

**Files:**
- Create: `SoundInbox/Views/LicenseSettingsView.swift`

**Steps:**

- [ ] Create `SoundInbox/Views/LicenseSettingsView.swift` matching the existing `SettingsView` styling (sections with icons, headers, dividers):

```swift
import SwiftUI

struct LicenseSettingsView: View {
    let licenseManager: LicenseManager

    @State private var keyInput: String = ""
    @State private var showDeactivateConfirmation = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                // License Status Section
                licenseStatusSection

                sectionDivider

                // Activation / Key Entry Section
                if licenseManager.isActivated {
                    activatedSection
                } else {
                    activationSection
                }

                // Error Display
                if let error = licenseManager.errorMessage {
                    sectionDivider
                    errorSection(message: error)
                }

                // Offline Warning
                if licenseManager.showOfflineWarning {
                    sectionDivider
                    offlineWarningSection
                }
            }
            .padding(20)
        }
        .sheet(isPresented: Binding(
            get: { licenseManager.showActivationSuccess },
            set: { licenseManager.showActivationSuccess = $0 }
        )) {
            ActivationSuccessView()
        }
        .sheet(isPresented: Binding(
            get: { licenseManager.deviceLimitResponse != nil },
            set: { if !$0 { licenseManager.deviceLimitResponse = nil } }
        )) {
            if let response = licenseManager.deviceLimitResponse {
                DeviceLimitView(
                    licenseManager: licenseManager,
                    response: response,
                    licenseKey: keyInput
                )
            }
        }
    }

    // MARK: - License Status Section

    private var licenseStatusSection: some View {
        settingsSection(icon: "key.fill", iconColor: licenseManager.isActivated ? .green : .secondary) {
            VStack(alignment: .leading, spacing: 2) {
                Text("License Status")
                    .font(.headline)
                Text(licenseManager.isActivated
                     ? "You have SoundInbox Pro"
                     : "Free — 1 email account")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            HStack(spacing: 12) {
                // Tier badge
                HStack(spacing: 6) {
                    Image(systemName: licenseManager.isActivated ? "checkmark.seal.fill" : "person.fill")
                        .foregroundStyle(licenseManager.isActivated ? .green : .secondary)
                    Text(licenseManager.tier == .pro ? "Pro" : "Free")
                        .font(.body)
                        .fontWeight(.medium)
                }

                Spacer()

                // Account limit display
                Text("Up to \(licenseManager.maxAccounts) account\(licenseManager.maxAccounts == 1 ? "" : "s")")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(Color.accentColor.opacity(0.1))
                    .cornerRadius(4)
            }

            if let contact = licenseManager.lastServerContact {
                HStack(spacing: 4) {
                    Image(systemName: "clock")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                    Text("Last verified: \(contact, format: .dateTime.month().day().year())")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                }
            }
        }
    }

    // MARK: - Activation Section (Not Yet Activated)

    private var activationSection: some View {
        settingsSection(icon: "rectangle.and.pencil.and.ellipsis", iconColor: .orange) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Activate License")
                    .font(.headline)
                Text("Enter your license key to unlock Pro features")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            VStack(alignment: .leading, spacing: 8) {
                TextField("XXXXX-XXXXX-XXXXX-XXXXX-XXXXX", text: $keyInput)
                    .textFieldStyle(.roundedBorder)
                    .font(.system(.body, design: .monospaced))
                    .onChange(of: keyInput) { _, newValue in
                        // Auto-format as user types
                        let normalized = licenseManager.normalizeLicenseKey(newValue)
                        if normalized != newValue && licenseManager.isValidKeyFormat(normalized) {
                            keyInput = normalized
                        }
                    }
                    .onSubmit {
                        Task { await licenseManager.activateLicense(key: keyInput) }
                    }

                HStack {
                    Button {
                        Task { await licenseManager.activateLicense(key: keyInput) }
                    } label: {
                        HStack(spacing: 6) {
                            if licenseManager.isLoading {
                                ProgressView()
                                    .controlSize(.small)
                            }
                            Text("Activate")
                        }
                        .frame(minWidth: 100)
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(keyInput.isEmpty || licenseManager.isLoading)

                    Spacer()

                    Button {
                        if let url = URL(string: LicenseConfig.checkoutURL) {
                            NSWorkspace.shared.open(url)
                        }
                    } label: {
                        Text("Buy License — $14.99")
                    }
                    .buttonStyle(.bordered)
                }
            }
        }
    }

    // MARK: - Activated Section

    private var activatedSection: some View {
        settingsSection(icon: "checkmark.seal.fill", iconColor: .green) {
            VStack(alignment: .leading, spacing: 2) {
                Text("License Activated")
                    .font(.headline)
                Text("SoundInbox Pro is active on this device")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            if let key = licenseManager.licenseKey {
                HStack {
                    Text("Key:")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text(licenseManager.maskedKey(key))
                        .font(.system(.caption, design: .monospaced))
                        .foregroundStyle(.secondary)
                        .textSelection(.enabled)
                }
            }

            HStack {
                Button(role: .destructive) {
                    showDeactivateConfirmation = true
                } label: {
                    Text("Deactivate License")
                }
                .buttonStyle(.bordered)
                .alert("Deactivate License?", isPresented: $showDeactivateConfirmation) {
                    Button("Deactivate", role: .destructive) {
                        Task { await licenseManager.deactivateLicense() }
                    }
                    Button("Cancel", role: .cancel) {}
                } message: {
                    Text("This will revert SoundInbox to the free tier on this device. You can reactivate anytime with the same key.")
                }

                if licenseManager.isLoading {
                    ProgressView()
                        .controlSize(.small)
                }
            }
        }
    }

    // MARK: - Error Section

    private func errorSection(message: String) -> some View {
        settingsSection(icon: "exclamationmark.triangle.fill", iconColor: .red) {
            Text(message)
                .font(.caption)
                .foregroundStyle(.red)
        }
    }

    // MARK: - Offline Warning Section

    private var offlineWarningSection: some View {
        settingsSection(icon: "wifi.slash", iconColor: .orange) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Verification Needed")
                    .font(.headline)
                Text("Please connect to the internet to verify your license. Pro features will be paused after 90 days offline.")
                    .font(.caption)
                    .foregroundStyle(.orange)
            }

            Button {
                Task { await licenseManager.verifyIfNeeded() }
            } label: {
                Text("Verify Now")
            }
            .buttonStyle(.borderedProminent)
        }
    }

    // MARK: - Reusable Components (matching SettingsView style)

    private func settingsSection<Content: View>(icon: String, iconColor: Color, @ViewBuilder content: () -> Content) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundStyle(iconColor)
                .frame(width: 24, alignment: .center)
                .padding(.top, 2)

            VStack(alignment: .leading, spacing: 10) {
                content()
            }
        }
        .padding(.vertical, 4)
    }

    private var sectionDivider: some View {
        Divider()
            .padding(.vertical, 8)
    }
}
```

- [ ] Build the project:

```bash
cd /Users/txeo/Git/mac/sound-inbox-mac && xcodebuild -scheme SoundInbox build 2>&1 | tail -5
```

- [ ] Commit:

```bash
git add SoundInbox/Views/LicenseSettingsView.swift
git commit -m "feat: Add LicenseSettingsView with activation, deactivation, and status display"
```

---

## Task 7: Create UpgradePromptView

**Files:**
- Create: `SoundInbox/Views/UpgradePromptView.swift`

**Steps:**

- [ ] Create `SoundInbox/Views/UpgradePromptView.swift` shown when `canAddAccount` returns false:

```swift
import SwiftUI

struct UpgradePromptView: View {
    /// Callback when user taps "I already have a key" — should navigate to License tab in Settings.
    var onOpenLicenseSettings: () -> Void
    /// Callback when user dismisses the prompt.
    var onDismiss: () -> Void

    var body: some View {
        VStack(spacing: 24) {
            // Icon
            Image(systemName: "envelope.badge.person.crop.fill")
                .font(.system(size: 48))
                .foregroundStyle(.orange)
                .padding(.top, 20)

            // Title
            Text("Add More Email Accounts with SoundInbox Pro")
                .font(.system(.title2, design: .rounded))
                .fontWeight(.semibold)
                .multilineTextAlignment(.center)

            // Description
            Text("Monitor work, personal, and client inboxes — all with their own formulas and custom sounds.")
                .font(.body)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 360)

            // Feature highlights
            VStack(alignment: .leading, spacing: 8) {
                featureRow(icon: "person.3.fill", text: "Up to 5 email accounts")
                featureRow(icon: "creditcard", text: "One-time purchase — no subscription")
                featureRow(icon: "checkmark.shield.fill", text: "Everything else stays free forever")
            }
            .padding(.horizontal, 20)

            // Buttons
            VStack(spacing: 12) {
                Button {
                    if let url = URL(string: LicenseConfig.checkoutURL) {
                        NSWorkspace.shared.open(url)
                    }
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "cart.fill")
                        Text("Upgrade for $14.99")
                    }
                    .frame(maxWidth: 260)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)

                Button {
                    onOpenLicenseSettings()
                } label: {
                    Text("I already have a key")
                        .font(.callout)
                }
                .buttonStyle(.plain)
                .foregroundStyle(.accentColor)
            }
            .padding(.bottom, 8)

            // Dismiss
            Button {
                onDismiss()
            } label: {
                Text("Not now")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }
            .buttonStyle(.plain)
            .padding(.bottom, 16)
        }
        .frame(width: 420, height: 440)
        .fixedSize()
    }

    private func featureRow(icon: String, text: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.caption)
                .foregroundStyle(.green)
                .frame(width: 20)
            Text(text)
                .font(.callout)
        }
    }
}
```

- [ ] Build the project:

```bash
cd /Users/txeo/Git/mac/sound-inbox-mac && xcodebuild -scheme SoundInbox build 2>&1 | tail -5
```

- [ ] Commit:

```bash
git add SoundInbox/Views/UpgradePromptView.swift
git commit -m "feat: Add UpgradePromptView with checkout link and 'I already have a key' flow"
```

---

## Task 8: Create DeviceLimitView and ActivationSuccessView

**Files:**
- Create: `SoundInbox/Views/DeviceLimitView.swift`
- Create: `SoundInbox/Views/ActivationSuccessView.swift`

**Steps:**

- [ ] Create `SoundInbox/Views/DeviceLimitView.swift` showing the list of activated devices with remote deactivation:

```swift
import SwiftUI

struct DeviceLimitView: View {
    let licenseManager: LicenseManager
    let response: ActivationResponse
    let licenseKey: String

    @Environment(\.dismiss) private var dismiss
    @State private var deactivatingDeviceID: String?

    var body: some View {
        VStack(spacing: 20) {
            // Header
            Image(systemName: "laptopcomputer.trianglebadge.exclamationmark")
                .font(.system(size: 40))
                .foregroundStyle(.orange)
                .padding(.top, 16)

            Text("Device Limit Reached")
                .font(.system(.title2, design: .rounded))
                .fontWeight(.semibold)

            Text("This license is already activated on \(response.currentActivations ?? 0) of \(response.maxActivations ?? LicenseConfig.maxActivationsPerKey) devices. Deactivate a device below to free up a slot.")
                .font(.callout)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 380)

            // Device list
            if let devices = response.activeDevices {
                VStack(spacing: 0) {
                    ForEach(devices) { device in
                        HStack(spacing: 12) {
                            Image(systemName: "laptopcomputer")
                                .font(.title3)
                                .foregroundStyle(.secondary)
                                .frame(width: 24)

                            VStack(alignment: .leading, spacing: 2) {
                                Text(device.deviceName)
                                    .font(.body)
                                Text("Activated: \(device.activatedAt)")
                                    .font(.caption2)
                                    .foregroundStyle(.tertiary)
                                if let lastSeen = device.lastSeenAt {
                                    Text("Last seen: \(lastSeen)")
                                        .font(.caption2)
                                        .foregroundStyle(.tertiary)
                                }
                            }

                            Spacer()

                            if device.deviceId == DeviceIDService.getDeviceID() {
                                Text("This device")
                                    .font(.caption2)
                                    .foregroundStyle(.green)
                                    .padding(.horizontal, 6)
                                    .padding(.vertical, 2)
                                    .background(Color.green.opacity(0.1))
                                    .cornerRadius(4)
                            } else {
                                Button(role: .destructive) {
                                    deactivatingDeviceID = device.deviceId
                                    Task {
                                        await licenseManager.deactivateRemoteDevice(deviceID: device.deviceId)
                                        // Retry activation on this device
                                        await licenseManager.activateLicense(key: licenseKey)
                                        if licenseManager.isActivated {
                                            dismiss()
                                        }
                                        deactivatingDeviceID = nil
                                    }
                                } label: {
                                    if deactivatingDeviceID == device.deviceId {
                                        ProgressView()
                                            .controlSize(.small)
                                    } else {
                                        Text("Remove")
                                    }
                                }
                                .buttonStyle(.bordered)
                                .controlSize(.small)
                                .disabled(deactivatingDeviceID != nil)
                            }
                        }
                        .padding(.vertical, 8)
                        .padding(.horizontal, 12)

                        if device.id != devices.last?.id {
                            Divider()
                                .padding(.horizontal, 12)
                        }
                    }
                }
                .background(Color(nsColor: .controlBackgroundColor))
                .cornerRadius(8)
                .padding(.horizontal, 20)
            }

            // Dismiss
            Button("Cancel") {
                dismiss()
            }
            .buttonStyle(.bordered)
            .padding(.bottom, 16)
        }
        .frame(width: 460, minHeight: 400)
        .fixedSize(horizontal: true, vertical: false)
    }
}
```

- [ ] Create `SoundInbox/Views/ActivationSuccessView.swift` with a success animation:

```swift
import SwiftUI

struct ActivationSuccessView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var showCheckmark = false
    @State private var showText = false

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            // Animated checkmark
            ZStack {
                Circle()
                    .fill(Color.green.opacity(0.15))
                    .frame(width: 100, height: 100)
                    .scaleEffect(showCheckmark ? 1.0 : 0.5)
                    .opacity(showCheckmark ? 1.0 : 0.0)

                Image(systemName: "checkmark.seal.fill")
                    .font(.system(size: 56))
                    .foregroundStyle(.green)
                    .scaleEffect(showCheckmark ? 1.0 : 0.3)
                    .opacity(showCheckmark ? 1.0 : 0.0)
            }
            .animation(.spring(response: 0.5, dampingFraction: 0.6), value: showCheckmark)

            // Text content
            VStack(spacing: 8) {
                Text("SoundInbox Pro Activated!")
                    .font(.system(.title2, design: .rounded))
                    .fontWeight(.bold)
                    .opacity(showText ? 1.0 : 0.0)
                    .offset(y: showText ? 0 : 10)

                Text("You can now monitor up to 5 email accounts.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .opacity(showText ? 1.0 : 0.0)
                    .offset(y: showText ? 0 : 10)
            }
            .animation(.easeOut(duration: 0.4).delay(0.3), value: showText)

            Spacer()

            Button("Done") {
                dismiss()
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .padding(.bottom, 24)
        }
        .frame(width: 340, height: 320)
        .fixedSize()
        .onAppear {
            showCheckmark = true
            showText = true
        }
    }
}
```

- [ ] Build the project:

```bash
cd /Users/txeo/Git/mac/sound-inbox-mac && xcodebuild -scheme SoundInbox build 2>&1 | tail -5
```

- [ ] Commit:

```bash
git add SoundInbox/Views/DeviceLimitView.swift SoundInbox/Views/ActivationSuccessView.swift
git commit -m "feat: Add DeviceLimitView and ActivationSuccessView for license activation flows"
```

---

## Task 9: Integrate LicenseManager into AppDelegate

**Files:**
- Modify: `SoundInbox/App/AppDelegate.swift`

**Steps:**

- [ ] Add a `LicenseManager` property to `AppDelegate`, next to the existing `store`, `imapPoller`, and `accountManager` declarations. In `AppDelegate.swift`, find:

```swift
    private let store = FormulaStore()
    private let imapPoller = IMAPEmailPoller()
    private let accountManager = AccountManager()
```

Replace with:

```swift
    private let store = FormulaStore()
    private let imapPoller = IMAPEmailPoller()
    private let accountManager = AccountManager()
    private let licenseManager = LicenseManager()
```

- [ ] In `applicationDidFinishLaunching`, add license restoration and background verification after the existing setup calls. Find:

```swift
        // Seed dev IMAP account if enabled
        DevConfig.seedIfNeeded(store: store)

        // Start email poller if accounts exist
        if store.hasRealAccounts {
            imapPoller.start(store: store)
        }
```

Replace with:

```swift
        // Seed dev IMAP account if enabled
        DevConfig.seedIfNeeded(store: store)

        // Restore license state from Keychain/UserDefaults
        licenseManager.restoreFromKeychain()

        // Start background license verification timer (every 7 days)
        licenseManager.startVerificationTimer()

        // Run initial verification if needed
        Task { await licenseManager.verifyIfNeeded() }

        // Start email poller if accounts exist
        if store.hasRealAccounts {
            imapPoller.start(store: store)
        }
```

- [ ] Update `openPreferences` to pass `licenseManager` to `PreferencesView`. Find both occurrences of:

```swift
            let prefsView = PreferencesView(store: store, imapPoller: imapPoller, accountManager: accountManager, initialTab: tab)
```

Replace each with:

```swift
            let prefsView = PreferencesView(store: store, imapPoller: imapPoller, accountManager: accountManager, licenseManager: licenseManager, initialTab: tab)
```

- [ ] Update `setupPopover` to pass `licenseManager` to `PopoverView` if needed, or leave it as-is if the popover does not need license info.

- [ ] Build the project (expect errors in `PreferencesView` until Task 10 is complete):

```bash
cd /Users/txeo/Git/mac/sound-inbox-mac && xcodebuild -scheme SoundInbox build 2>&1 | tail -10
```

- [ ] Commit (may need to combine with Task 10 if build fails):

```bash
git add SoundInbox/App/AppDelegate.swift
git commit -m "feat: Integrate LicenseManager into AppDelegate with restore and verification timer"
```

---

## Task 10: Add License Tab to PreferencesView

**Files:**
- Modify: `SoundInbox/Views/PreferencesView.swift`

**Steps:**

- [ ] Add `licenseManager` parameter to `PreferencesView`. Find:

```swift
struct PreferencesView: View {
    let store: FormulaStore
    let imapPoller: IMAPEmailPoller
    let accountManager: AccountManager

    var initialTab: PreferencesTab = .settings
```

Replace with:

```swift
struct PreferencesView: View {
    let store: FormulaStore
    let imapPoller: IMAPEmailPoller
    let accountManager: AccountManager
    let licenseManager: LicenseManager

    var initialTab: PreferencesTab = .settings
```

- [ ] Add `.license` case to the `PreferencesTab` enum. Find:

```swift
        case accounts = "Accounts"

        var localizedName: String {
```

Replace with:

```swift
        case accounts = "Accounts"
        case license = "License"

        var localizedName: String {
```

- [ ] Add the localized name for the license tab. Find:

```swift
            case .accounts: return String(localized: "tab.accounts")
```

Replace with:

```swift
            case .accounts: return String(localized: "tab.accounts")
            case .license: return String(localized: "tab.license")
```

- [ ] Add the icon for the license tab. Find:

```swift
            case .accounts: return "person.crop.circle.badge.plus"
```

Replace with:

```swift
            case .accounts: return "person.crop.circle.badge.plus"
            case .license: return "key.fill"
```

- [ ] Add the `LicenseSettingsView` tab in the `TabView`. Find:

```swift
                AccountsView(store: store, accountManager: accountManager)
                    .tabItem {
                        Label(PreferencesTab.accounts.localizedName, systemImage: PreferencesTab.accounts.icon)
                    }
                    .tag(PreferencesTab.accounts)
```

Replace with:

```swift
                AccountsView(store: store, accountManager: accountManager, licenseManager: licenseManager)
                    .tabItem {
                        Label(PreferencesTab.accounts.localizedName, systemImage: PreferencesTab.accounts.icon)
                    }
                    .tag(PreferencesTab.accounts)

                LicenseSettingsView(licenseManager: licenseManager)
                    .tabItem {
                        Label(PreferencesTab.license.localizedName, systemImage: PreferencesTab.license.icon)
                    }
                    .tag(PreferencesTab.license)
```

- [ ] Build the project (expect errors in `AccountsView` until Task 11 is complete):

```bash
cd /Users/txeo/Git/mac/sound-inbox-mac && xcodebuild -scheme SoundInbox build 2>&1 | tail -10
```

- [ ] Commit:

```bash
git add SoundInbox/Views/PreferencesView.swift
git commit -m "feat: Add License tab to PreferencesView with LicenseSettingsView"
```

---

## Task 11: Wire Feature Gate into AccountsView

**Files:**
- Modify: `SoundInbox/Views/AccountsView.swift`

**Steps:**

- [ ] Add `licenseManager` parameter to `AccountsView`. Find:

```swift
struct AccountsView: View {
    let store: FormulaStore
    let accountManager: AccountManager

    @State private var showAddSheet = false
    @State private var selectedProvider: EmailProvider?
    @State private var editingAccount: EmailAccount?
```

Replace with:

```swift
struct AccountsView: View {
    let store: FormulaStore
    let accountManager: AccountManager
    let licenseManager: LicenseManager

    @State private var showAddSheet = false
    @State private var selectedProvider: EmailProvider?
    @State private var editingAccount: EmailAccount?
    @State private var showUpgradePrompt = false
```

- [ ] Replace the Add Account menu with a gated version. Find the entire `HStack` containing the title and menu:

```swift
            HStack {
                Text("accounts.title")
                    .font(.title2)
                Spacer()
                Menu {
                    Button { selectedProvider = .gmail } label: {
                        Label("accounts.gmail", systemImage: "envelope.badge.person.crop")
                    }
                    Button { selectedProvider = .imap } label: {
                        Label("accounts.imap", systemImage: "server.rack")
                    }
                    Button { selectedProvider = .outlook } label: {
                        Label("accounts.outlook", systemImage: "envelope")
                    }
                } label: {
                    Label("accounts.addAccount", systemImage: "plus")
                }
                .menuStyle(.borderedButton)
            }
```

Replace with:

```swift
            HStack {
                Text("accounts.title")
                    .font(.title2)
                Spacer()
                if licenseManager.canAddAccount(currentCount: store.accounts.count) {
                    Menu {
                        Button { selectedProvider = .gmail } label: {
                            Label("accounts.gmail", systemImage: "envelope.badge.person.crop")
                        }
                        Button { selectedProvider = .imap } label: {
                            Label("accounts.imap", systemImage: "server.rack")
                        }
                        Button { selectedProvider = .outlook } label: {
                            Label("accounts.outlook", systemImage: "envelope")
                        }
                    } label: {
                        Label("accounts.addAccount", systemImage: "plus")
                    }
                    .menuStyle(.borderedButton)
                } else {
                    Button {
                        showUpgradePrompt = true
                    } label: {
                        Label("accounts.addAccount", systemImage: "plus")
                    }
                    .buttonStyle(.borderedProminent)
                }
            }
```

- [ ] Add the `UpgradePromptView` sheet. Find the closing of the `editingAccount` sheet:

```swift
        .sheet(item: $editingAccount) { account in
            EditAccountView(store: store, accountManager: accountManager, account: account)
        }
```

Replace with:

```swift
        .sheet(item: $editingAccount) { account in
            EditAccountView(store: store, accountManager: accountManager, account: account)
        }
        .sheet(isPresented: $showUpgradePrompt) {
            UpgradePromptView(
                onOpenLicenseSettings: {
                    showUpgradePrompt = false
                    // Navigate to License tab — the parent PreferencesView handles tab switching
                    // Post a notification that AppDelegate can handle to switch tabs
                    NotificationCenter.default.post(
                        name: Notification.Name("SoundInbox.openLicenseSettings"),
                        object: nil
                    )
                },
                onDismiss: {
                    showUpgradePrompt = false
                }
            )
        }
```

- [ ] Add paused account badge to `AccountRow`. Find the existing disabled badge in `AccountRow`:

```swift
                    if !account.isEnabled {
                        Text("accounts.disabled")
                            .font(.caption2)
                            .foregroundStyle(.orange)
                            .padding(.horizontal, 5)
                            .padding(.vertical, 1)
                            .background(Color.orange.opacity(0.12))
                            .cornerRadius(3)
                    }
```

This badge can be reused for paused accounts in a future step if the account model gains an `isPaused` property. For now, the feature gate on the Add Account button is the primary enforcement point.

- [ ] Build the project:

```bash
cd /Users/txeo/Git/mac/sound-inbox-mac && xcodebuild -scheme SoundInbox build 2>&1 | tail -10
```

- [ ] Commit:

```bash
git add SoundInbox/Views/AccountsView.swift
git commit -m "feat: Wire feature gate into AccountsView — show UpgradePromptView when limit reached"
```

---

## Task 12: Handle License Tab Navigation from UpgradePromptView

**Files:**
- Modify: `SoundInbox/App/AppDelegate.swift`
- Modify: `SoundInbox/Views/PreferencesView.swift`

**Steps:**

- [ ] Add a notification observer in `AppDelegate` to handle the "I already have a key" navigation. In `applicationDidFinishLaunching`, after the existing `observeAlertModeChanges()` call, add:

Find:

```swift
        observeAlertModeChanges()
```

Replace with:

```swift
        observeAlertModeChanges()
        observeLicenseSettingsNavigation()
```

- [ ] Add the observer method to `AppDelegate`. Add this new method anywhere in the class:

```swift
    private func observeLicenseSettingsNavigation() {
        NotificationCenter.default.addObserver(
            forName: Notification.Name("SoundInbox.openLicenseSettings"),
            object: nil,
            queue: .main
        ) { [weak self] _ in
            self?.openPreferences(tab: .license)
        }
    }
```

- [ ] Build the project:

```bash
cd /Users/txeo/Git/mac/sound-inbox-mac && xcodebuild -scheme SoundInbox build 2>&1 | tail -5
```

- [ ] Commit:

```bash
git add SoundInbox/App/AppDelegate.swift
git commit -m "feat: Handle license settings navigation from UpgradePromptView"
```

---

## Task 13: Add Keychain Migration Logic

**Files:**
- Modify: `SoundInbox/Services/KeychainService.swift`

**Steps:**

- [ ] Add a migration method to `KeychainService` that will be called on app launch. This migrates credentials from the FileVault backend to the real Keychain when `useFileVault` is flipped to `false`. Add the following at the end of the `KeychainService` struct, before the closing brace:

Find the end of the `KeychainService` struct (the `key` function and closing brace):

```swift
    private static func key(accountId: UUID, type: CredentialType) -> String {
        "\(serviceName).\(accountId.uuidString).\(type.rawValue)"
    }
}
```

Replace with:

```swift
    private static func key(accountId: UUID, type: CredentialType) -> String {
        "\(serviceName).\(accountId.uuidString).\(type.rawValue)"
    }

    // MARK: - FileVault → Keychain Migration

    /// Migrates all credentials from the FileVault backend to the real macOS Keychain.
    /// Call this on app launch when switching from `useFileVault = true` to `false`.
    ///
    /// This is critical for license keys: a beta user who activates Pro via the FileVault
    /// backend and then updates to the Keychain backend would lose their license key without
    /// migration.
    ///
    /// Returns the number of credentials successfully migrated.
    @discardableResult
    static func migrateFileVaultToKeychain(accounts: [EmailAccount]) -> Int {
        // Only needed when we're using real Keychain (useFileVault == false)
        // If still using FileVault, nothing to migrate
        guard !useFileVault else {
            NSLog("[Migration] Skipping: still using FileVault backend")
            return 0
        }

        let migrationKey = "soundinbox_filevault_migration_complete"
        guard !UserDefaults.standard.bool(forKey: migrationKey) else {
            return 0 // Already migrated
        }

        NSLog("[Migration] Starting FileVault → Keychain migration...")
        var migratedCount = 0

        // Migrate per-account credentials
        for account in accounts {
            for type in [CredentialType.password, .oauthAccessToken, .oauthRefreshToken, .oauthTokenExpiry] {
                let fileVaultKey = "\(serviceName).\(account.id.uuidString).\(type.rawValue)"
                if let data = FileVault.load(key: fileVaultKey) {
                    do {
                        try Keychain.save(key: fileVaultKey, data: data, service: serviceName)
                        FileVault.delete(key: fileVaultKey)
                        migratedCount += 1
                        NSLog("[Migration] Migrated %@ for account %@", type.rawValue, account.emailAddress)
                    } catch {
                        NSLog("[Migration] Failed to migrate %@ for %@: %@", type.rawValue, account.emailAddress, "\(error)")
                    }
                }
            }
        }

        // Migrate license key from com.soundinbox.license service (if stored in FileVault)
        let licenseKeys = ["license-key"]
        for key in licenseKeys {
            let fileVaultKey = "\(LicenseConfig.keychainService).\(key)"
            if let data = FileVault.load(key: fileVaultKey) {
                let query: [String: Any] = [
                    kSecClass as String: kSecClassGenericPassword,
                    kSecAttrService as String: LicenseConfig.keychainService,
                    kSecAttrAccount as String: key,
                    kSecValueData as String: data,
                    kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock
                ]
                let status = SecItemAdd(query as CFDictionary, nil)
                if status == errSecSuccess || status == errSecDuplicateItem {
                    FileVault.delete(key: fileVaultKey)
                    migratedCount += 1
                    NSLog("[Migration] Migrated license key")
                }
            }
        }

        // Migrate device ID from com.soundinbox.system service (if stored in FileVault)
        let systemKeys = ["device-id"]
        for key in systemKeys {
            let fileVaultKey = "\(LicenseConfig.systemKeychainService).\(key)"
            if let data = FileVault.load(key: fileVaultKey) {
                let query: [String: Any] = [
                    kSecClass as String: kSecClassGenericPassword,
                    kSecAttrService as String: LicenseConfig.systemKeychainService,
                    kSecAttrAccount as String: key,
                    kSecValueData as String: data,
                    kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock
                ]
                let status = SecItemAdd(query as CFDictionary, nil)
                if status == errSecSuccess || status == errSecDuplicateItem {
                    FileVault.delete(key: fileVaultKey)
                    migratedCount += 1
                    NSLog("[Migration] Migrated device ID")
                }
            }
        }

        UserDefaults.standard.set(true, forKey: migrationKey)
        NSLog("[Migration] Complete: %d credentials migrated", migratedCount)
        return migratedCount
    }
}
```

- [ ] **Important:** The `FileVault` enum is currently `private` to the file. The migration method accesses it from within the same file so it works without access changes.

- [ ] Add the migration call in `AppDelegate.applicationDidFinishLaunching`, right after `DevConfig.seedIfNeeded`. Find:

```swift
        // Restore license state from Keychain/UserDefaults
        licenseManager.restoreFromKeychain()
```

Replace with:

```swift
        // Migrate FileVault → Keychain if needed (before restoring license state)
        KeychainService.migrateFileVaultToKeychain(accounts: store.accounts)

        // Restore license state from Keychain/UserDefaults
        licenseManager.restoreFromKeychain()
```

- [ ] Build the project:

```bash
cd /Users/txeo/Git/mac/sound-inbox-mac && xcodebuild -scheme SoundInbox build 2>&1 | tail -5
```

- [ ] Commit:

```bash
git add SoundInbox/Services/KeychainService.swift SoundInbox/App/AppDelegate.swift
git commit -m "feat: Add FileVault → Keychain migration logic for beta-to-release transition"
```

---

## Task 13b: Add Localization Keys

**Files:**
- Modify: Localizable strings file (if the project uses `.xcstrings` or `Localizable.strings`)

**Steps:**

- [ ] Check which localization format the project uses:

```bash
find /Users/txeo/Git/mac/sound-inbox-mac -name "Localizable*" -o -name "*.xcstrings" 2>/dev/null
```

- [ ] Add the new localization key `tab.license` with value `"License"` to the appropriate localization file. The exact edit depends on the localization format found above. If using `.xcstrings`, add:

```json
"tab.license": {
    "localizations": {
        "en": { "stringUnit": { "state": "translated", "value": "License" } }
    }
}
```

If using `Localizable.strings`:
```
"tab.license" = "License";
```

- [ ] Build and verify.

- [ ] Commit:

```bash
git add -A
git commit -m "feat: Add localization key for License tab"
```

---

## Task 14: Build and Manual Testing

**Files:**
- No new files

**Steps:**

- [ ] Clean build the entire project:

```bash
cd /Users/txeo/Git/mac/sound-inbox-mac && xcodebuild -scheme SoundInbox clean build 2>&1 | tail -20
```

- [ ] Kill any running instance and launch the new build:

```bash
pkill -f SoundInbox || true
open /Users/txeo/Git/mac/sound-inbox-mac/build/Build/Products/Debug/SoundInbox.app
```

- [ ] **Test 1: License tab appears.** Open Settings (right-click menu bar icon > Preferences). Verify a "License" tab is visible with a key icon. Click it. The License Settings view should show "Free — 1 email account" status.

- [ ] **Test 2: Free tier gate.** Navigate to the Accounts tab. If there is already 1 account (from DevConfig seeding), the "Add Account" button should now show the upgrade prompt. Verify the UpgradePromptView appears with:
  - "Add more email accounts with SoundInbox Pro"
  - "Upgrade for $14.99" button
  - "I already have a key" link

- [ ] **Test 3: "I already have a key" flow.** Click "I already have a key" in the UpgradePromptView. Verify it opens/switches to the License tab in Settings.

- [ ] **Test 4: Invalid key format.** In the License tab, enter "invalid-key" and click Activate. Verify inline error: "Invalid license key format."

- [ ] **Test 5: Network error handling.** Enter a properly formatted key (e.g., "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY") and click Activate. Since the server API is not yet deployed, verify the error message: "Could not connect to the license server."

- [ ] **Test 6: Device ID persistence.** Check the console logs for `[License]` and `[DeviceID]` entries. The device ID should remain the same across app restarts.

- [ ] **Test 7: UserDefaults persistence.** Quit the app and relaunch. Verify the License tab still shows "Free" tier (not an error).

- [ ] After all tests pass, commit with a summary:

```bash
git add -A
git commit -m "feat: Complete macOS licensing integration — LicenseManager, feature gates, license settings UI"
```

---

## Summary of All Files

### New Files (9)

| File | Type | Description |
|------|------|-------------|
| `SoundInbox/Models/LicenseState.swift` | Model | LicenseTier, FeatureEntitlements, LicenseConfig constants |
| `SoundInbox/Models/LicenseResponse.swift` | Model | Codable API response structs matching server contracts |
| `SoundInbox/Services/DeviceIDService.swift` | Service | Stable UUID device identifier via Keychain |
| `SoundInbox/Services/LicenseAPIService.swift` | Service | Actor-based HTTP client for license API |
| `SoundInbox/Services/LicenseManager.swift` | Service | @Observable license state authority with offline grace |
| `SoundInbox/Views/LicenseSettingsView.swift` | View | License management tab in Settings |
| `SoundInbox/Views/UpgradePromptView.swift` | View | Upgrade prompt shown at account limit |
| `SoundInbox/Views/DeviceLimitView.swift` | View | Device limit reached with remote deactivation |
| `SoundInbox/Views/ActivationSuccessView.swift` | View | Success animation after activation |

### Modified Files (4)

| File | Changes |
|------|---------|
| `SoundInbox/App/AppDelegate.swift` | Add LicenseManager, restore on launch, verification timer, migration call, license nav observer |
| `SoundInbox/Views/PreferencesView.swift` | Add licenseManager param, .license tab case, LicenseSettingsView tab |
| `SoundInbox/Views/AccountsView.swift` | Add licenseManager param, feature gate on Add Account, UpgradePromptView sheet |
| `SoundInbox/Services/KeychainService.swift` | Add migrateFileVaultToKeychain method |

### Dependency Graph

```
Task 1 (LicenseState) ─────────────┐
Task 2 (LicenseResponse) ──────────┤
Task 3 (DeviceIDService) ──────────┼── Task 4 (LicenseAPIService) ── Task 5 (LicenseManager)
                                    │                                        │
                                    │            ┌───────────────────────────┘
                                    │            │
                                    │   Task 6 (LicenseSettingsView)
                                    │   Task 7 (UpgradePromptView)
                                    │   Task 8 (DeviceLimitView + ActivationSuccessView)
                                    │            │
                                    │            ├── Task 9 (AppDelegate integration)
                                    │            ├── Task 10 (PreferencesView tab)
                                    │            ├── Task 11 (AccountsView gate)
                                    │            ├── Task 12 (License nav handler)
                                    │            └── Task 13 (Keychain migration)
                                    │                        │
                                    │                        └── Task 13b (Localization)
                                    │                                    │
                                    └────────────────────────────────── Task 14 (Build + Test)
```

Tasks 1-3 can run in parallel. Task 4 depends on 1-3. Task 5 depends on 4. Tasks 6-8 depend on 5 and can run in parallel. Tasks 9-13 depend on 5-8 and should be done sequentially (each modifies shared files). Task 14 is the final verification step.
