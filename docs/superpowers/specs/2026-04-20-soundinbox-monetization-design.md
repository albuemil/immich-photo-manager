# SoundInbox Monetization Design Specification

**Date:** 2026-04-20
**Status:** Draft
**Product:** SoundInbox (macOS menu bar app)
**Price:** $14.99 one-time purchase via Lemon Squeezy
**Hosting:** drolosoft.com (extension of existing Go web app)
**Reference:** Commando license system at `/Users/txeo/Git/mac/go/commando-web/`

---

## 1. Architecture Overview

### 1.1 System Topology

```
                      +---------------------+
                      |   Lemon Squeezy     |
                      |   (payment page)    |
                      +----------+----------+
                                 |
                          webhook (HTTPS)
                                 |
                      +----------v----------+
                      |   drolosoft.com     |
                      |   Go web server     |
                      |                     |
                      | /api/soundinbox/... |
                      | /soundinbox/...     |
                      | /admin/soundinbox/  |
                      +----------+----------+
                                 |
                            JSON API
                                 |
                      +----------v----------+
                      |   SoundInbox.app    |
                      |   macOS 14+         |
                      |   Swift 6.0         |
                      +---------------------+
```

### 1.2 Integration Strategy

The Drolosoft web server currently has no database. Adding SoundInbox licensing requires:

1. **Add SQLite database** to the Drolosoft server (same as Commando's approach)
2. **New Go package** `internal/licensing` — product-agnostic license engine, reusable across SoundInbox and eventually Commando
3. **Product-specific handlers** in `internal/handlers/soundinbox.go`
4. **New config fields** in `internal/config/config.go` for license/payment settings

### 1.3 Package Layout (New Files in Drolosoft)

```
internal/
  config/config.go          (extend with license fields)
  licensing/
    keygen.go               (ported from commando-web, shared)
    models.go               (License, Activation, Order, WebhookLog)
    repository.go           (SQLite CRUD)
    migrations.go           (embedded SQL)
    migrations/
      001_create_tables.sql
  handlers/
    soundinbox.go           (product pages: landing, pricing, download)
    soundinbox_api.go       (license API endpoints)
    soundinbox_webhook.go   (Lemon Squeezy webhook)
    soundinbox_admin.go     (admin dashboard)
  services/
    email/
      email.go              (SMTP delivery, reusable)
      templates_soundinbox.go (SoundInbox-branded templates)
    webhook/
      verify.go             (HMAC-SHA256 signature verification)
  middleware/
    ratelimit.go            (already exists, extend with API limits)
    basicauth.go            (new: admin auth)
    cors.go                 (new: origin checking for API)
```

### 1.4 Database Isolation

Single SQLite database file at `data/drolosoft.db`. Tables are prefixed to allow multi-product usage:

- `si_licenses` (SoundInbox licenses)
- `si_activations` (SoundInbox device activations)
- `si_orders` (SoundInbox Lemon Squeezy orders)
- `si_webhook_logs` (SoundInbox webhook audit trail)

Future Commando migration would use `cmd_` prefix. The `internal/licensing` package is product-agnostic and receives a table prefix parameter.

---

## 2. Database Schema

### 2.1 Migration: `001_create_soundinbox_tables.sql`

```sql
-- SoundInbox Licenses
CREATE TABLE IF NOT EXISTS si_licenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key TEXT NOT NULL UNIQUE,
    order_id TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    customer_name TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'revoked', 'refunded')),
    max_activations INTEGER NOT NULL DEFAULT 3,
    current_activations INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    revoked_at TEXT,
    email_sent INTEGER NOT NULL DEFAULT 0,
    email_sent_at TEXT,
    email_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_si_licenses_key ON si_licenses(license_key);
CREATE INDEX IF NOT EXISTS idx_si_licenses_email ON si_licenses(customer_email);
CREATE INDEX IF NOT EXISTS idx_si_licenses_order ON si_licenses(order_id);

-- SoundInbox Device Activations
CREATE TABLE IF NOT EXISTS si_activations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key TEXT NOT NULL,
    device_id TEXT NOT NULL,
    device_name TEXT,
    device_model TEXT,
    os_version TEXT,
    app_version TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'deactivated')),
    activated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    deactivated_at TEXT,
    last_seen_at TEXT,
    UNIQUE(license_key, device_id),
    FOREIGN KEY (license_key) REFERENCES si_licenses(license_key)
);

CREATE INDEX IF NOT EXISTS idx_si_activations_license ON si_activations(license_key);
CREATE INDEX IF NOT EXISTS idx_si_activations_device ON si_activations(device_id);

-- SoundInbox Orders (from Lemon Squeezy webhooks)
CREATE TABLE IF NOT EXISTS si_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL UNIQUE,
    product_id TEXT,
    variant_id TEXT,
    customer_email TEXT NOT NULL,
    customer_name TEXT,
    status TEXT NOT NULL DEFAULT 'paid' CHECK(status IN ('paid', 'refunded', 'failed')),
    total_amount INTEGER NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    event_name TEXT NOT NULL,
    webhook_payload TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    refunded_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_si_orders_email ON si_orders(customer_email);
CREATE INDEX IF NOT EXISTS idx_si_orders_order ON si_orders(order_id);

-- SoundInbox Webhook Audit Log
CREATE TABLE IF NOT EXISTS si_webhook_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name TEXT NOT NULL,
    signature_valid INTEGER NOT NULL DEFAULT 0,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'received' CHECK(status IN ('received', 'processing', 'completed', 'failed')),
    error_message TEXT,
    order_id TEXT,
    license_key TEXT,
    received_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    processed_at TEXT
);

-- Updated_at trigger
CREATE TRIGGER IF NOT EXISTS si_licenses_updated_at
    AFTER UPDATE ON si_licenses
    FOR EACH ROW
BEGIN
    UPDATE si_licenses SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS si_orders_updated_at
    AFTER UPDATE ON si_orders
    FOR EACH ROW
BEGIN
    UPDATE si_orders SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = OLD.id;
END;
```

---

## 3. Feature Gates

### 3.1 Free vs Pro Split

The gate is simple: **email account limit**. Free users get the full product with one account. Pro unlocks multiple accounts.

| Feature | Free | Pro ($14.99) |
|---------|------|--------------|
| **Email accounts** | **1 account** | **Up to 5 accounts** |
| Formulas (pre-built) | All 9 | All 9 |
| Custom rules | Unlimited | Unlimited |
| Rule conditions | Unlimited | Unlimited |
| Condition operators | All 6 | All 6 |
| VIP sender list | Unlimited | Unlimited |
| Do Not Disturb schedule | Full support | Full support |
| Sound customization | All (built-in + custom) | All (built-in + custom) |
| Match history | Full | Full |
| Polling interval | All options | All options |
| Alert types | Sound + speech | Sound + speech |

### 3.2 Rationale

The free tier is a **fully functional product**. No feature crippling, no artificial limits on power features. Users get the complete SoundInbox experience with one email account.

The moment they need a second account (work + personal, or multiple business accounts), they hit the single paywall: $14.99 for up to 5 accounts. This is a natural, fair gate:
- Users who only have one email never feel limited
- Users with multiple accounts have a clear reason to pay
- No "trial" feeling — free is a real product
- Simple to understand, simple to enforce

### 3.3 Feature Gate Constants (Swift)

```swift
enum FeatureGate {
    static let freeMaxAccounts = 1
    static let proMaxAccounts = 5
}
```

### 3.4 Feature Gate Constants (Go API response)

The validate/activate API response includes a `features` object so the client knows its entitlements:

```json
{
  "valid": true,
  "status": "active",
  "features": {
    "max_accounts": 5
  }
}
```

Value `-1` means unlimited. The client caches this and enforces locally.

---

## 4. Web Backend — Route Definitions

### 4.1 Public Pages

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/soundinbox.html` | `SiteHandler.SoundInbox` | Landing page (already exists in registry) |
| GET | `/soundinbox/pricing` | `SoundInboxHandler.Pricing` | Pricing comparison (Free vs Pro) |
| GET | `/soundinbox/download` | `SoundInboxHandler.Download` | Download page with Homebrew/DMG instructions |
| GET | `/soundinbox/privacy` | `SoundInboxHandler.Privacy` | Google OAuth privacy policy (required) |
| GET | `/soundinbox/changelog` | `SoundInboxHandler.Changelog` | Version history |

### 4.2 License API

| Method | Path | Handler | Rate Limit |
|--------|------|---------|------------|
| POST | `/api/soundinbox/licenses/validate` | `ValidateLicense` | 60/min per IP + 10/min per license key |
| POST | `/api/soundinbox/licenses/activate` | `ActivateLicense` | 60/min per IP + 10/min per license key |
| POST | `/api/soundinbox/licenses/deactivate` | `DeactivateLicense` | 60/min per IP + 10/min per license key |
| GET | `/api/soundinbox/licenses/{key}` | `GetLicense` | 60/min per IP |
| GET | `/api/soundinbox/health` | `HealthCheck` | No limit |

All API handlers MUST check `r.Method` and reject unsupported methods with 405. Consider using a method-aware router (chi) to eliminate this boilerplate.

### 4.3 Webhook

| Method | Path | Handler | Rate Limit |
|--------|------|---------|------------|
| POST | `/api/soundinbox/webhooks/lemonsqueezy` | `WebhookHandler` | 100/min |

### 4.4 Admin Panel

| Method | Path | Handler | Auth |
|--------|------|---------|------|
| GET | `/admin/soundinbox/` | `AdminDashboard` | Basic Auth |
| GET | `/admin/soundinbox/licenses` | `AdminLicenseList` | Basic Auth |
| GET | `/admin/soundinbox/licenses/{key}` | `AdminLicenseDetail` | Basic Auth |
| POST | `/admin/soundinbox/licenses/generate` | `AdminGenerateLicense` | Basic Auth |
| POST | `/admin/soundinbox/licenses/{key}/revoke` | `AdminRevokeLicense` | Basic Auth |
| GET | `/admin/soundinbox/orders` | `AdminOrderList` | Basic Auth |
| GET | `/admin/soundinbox/webhooks` | `AdminWebhookLogs` | Basic Auth |

---

## 5. API Contracts

### 5.1 POST `/api/soundinbox/licenses/validate`

**Request:**
```json
{
  "license_key": "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY"
}
```

**Response (200 OK — valid):**
```json
{
  "valid": true,
  "message": "License key is valid and active",
  "status": "active",
  "tier": "pro",
  "server_time": "2026-04-20T15:30:00Z",
  "features": {
    "max_accounts": 5
  }
}
```

**Design decision:** The `features` object only includes fields that actually differ between tiers. Since the only gate is account count, only `max_accounts` is returned. The `tier` field (`"free"` or `"pro"`) is included for client convenience. All other features (formulas, rules, sounds, etc.) are unlimited in both tiers and need not be communicated via API.

**Response (200 OK — invalid/revoked):**
```json
{
  "valid": false,
  "message": "License is revoked",
  "status": "revoked",
  "features": null
}
```

**Response (404 — not found):**
```json
{
  "valid": false,
  "message": "License key not found",
  "status": "not_found"
}
```

**Response (400 — bad format):**
```json
{
  "valid": false,
  "message": "Invalid license key format"
}
```

### 5.2 POST `/api/soundinbox/licenses/activate`

**Request:**
```json
{
  "license_key": "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY",
  "device_id": "C5D4E3F2-A1B0-4C5D-8E9F-0A1B2C3D4E5F",
  "device_name": "Juan's MacBook Pro",
  "device_model": "MacBookPro18,1",
  "os_version": "15.2",
  "app_version": "1.0.0"
}
```

**Input validation:** `device_name` and `device_model` must be validated: max 100 characters, no control characters, HTML-escaped before storage. These fields are displayed in the admin panel — without validation they are stored XSS vectors.

**Response (201 Created — success):**
```json
{
  "success": true,
  "message": "Device activated successfully",
  "activation_id": "42",
  "activated_at": "2026-04-20T10:30:00Z",
  "device_name": "Juan's MacBook Pro",
  "tier": "pro",
  "features": {
    "max_accounts": 5
  }
}
```

**Response (200 OK — already activated on this device):**
```json
{
  "success": true,
  "message": "Device already activated",
  "activation_id": "42",
  "activated_at": "2026-04-20T10:30:00Z",
  "device_name": "Juan's MacBook Pro",
  "tier": "pro",
  "features": {
    "max_accounts": 5
  }
}
```

**Response (403 Forbidden — limit reached):**
```json
{
  "success": false,
  "error": "Activation limit reached",
  "message": "This license is already activated on 3 device(s). Please deactivate a device to activate a new one.",
  "current_activations": 3,
  "max_activations": 3,
  "active_devices": [
    {
      "device_id": "...",
      "device_name": "Juan's MacBook Pro",
      "activated_at": "2026-04-20T10:30:00Z",
      "last_seen_at": "2026-04-20T15:00:00Z"
    }
  ]
}
```

### 5.3 POST `/api/soundinbox/licenses/deactivate`

**Request:**
```json
{
  "license_key": "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY",
  "device_id": "C5D4E3F2-A1B0-4C5D-8E9F-0A1B2C3D4E5F"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Device deactivated successfully",
  "license": {
    "license_key": "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY",
    "current_activations": 2,
    "max_activations": 3
  }
}
```

### 5.4 GET `/api/soundinbox/licenses/{key}?device_id={device_id}`

Requires `device_id` query parameter for authentication. Only returns information relevant to the requesting device.

**Response (200 OK):**
```json
{
  "license": {
    "license_key": "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY",
    "status": "active",
    "max_activations": 3,
    "current_activations": 1,
    "created_at": "2026-04-20T10:30:00Z"
  },
  "your_activation": {
    "device_id": "C5D4E3F2-...",
    "device_name": "Juan's MacBook Pro",
    "status": "active",
    "activated_at": "2026-04-20T10:30:00Z"
  }
}
```

**Response (403 — device not activated on this license):**
```json
{
  "error": "Device not found for this license"
}
```

**Note:** Full license details including customer email and all activations are only available via the admin panel (`/admin/soundinbox/licenses/{key}`). The public endpoint intentionally omits PII.

### 5.5 POST `/api/soundinbox/webhooks/lemonsqueezy`

**Headers:**
- `X-Signature`: HMAC-SHA256 hex digest
- `Content-Type`: application/json

**Request body:** Raw Lemon Squeezy webhook payload (see Commando's `webhook.LemonSqueezyWebhook` struct)

**Response (200 OK — always respond quickly):**
```json
{
  "status": "accepted"
}
```

Processing happens asynchronously via goroutine.

---

## 6. License Key Generation

Ported directly from Commando with no changes:

- **Format:** `XXXXX-XXXXX-XXXXX-XXXXX-XXXXX` (25 chars + 4 hyphens = 29 total)
- **Charset:** `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` (Base32, no ambiguous O/I/L/0/1)
- **Source:** `crypto/rand`
- **Normalization:** Trim whitespace, uppercase, remove non-alphanumeric, re-insert hyphens
- **Max activations per key:** 3 devices (SoundInbox default, configurable per product)

---

## 7. Webhook Processing Flow

1. **Receive** POST at `/api/soundinbox/webhooks/lemonsqueezy`
2. **Verify** HMAC-SHA256 signature (`X-Signature` header vs. computed digest using `SOUNDINBOX_WEBHOOK_SECRET`)
3. **Parse** JSON payload into `LemonSqueezyWebhook` struct
4. **Validate** required fields (event_name, user_email, status == "paid", total > 0)
5. **Respond** HTTP 200 `{"status": "accepted"}` (must respond within 5s per Lemon Squeezy SLA)
6. **Process async** (goroutine — wrap in `defer func() { if r := recover(); r != nil { log.Error(...) } }()` for panic safety. Consider using a buffered channel (capacity 100) instead of bare goroutines to bound concurrency):
   a. Log webhook to `si_webhook_logs`
   b. If `event_name == "order_created"` and status is paid and not refunded:
      - **Idempotency check:** Query `SELECT license_key FROM si_licenses WHERE order_id = ?`
        - If license already exists: skip generation. If `email_sent = 0`, resend email. Log as idempotent replay in `si_webhook_logs`.
        - If no license exists: proceed with generation below.
      - Store order in `si_orders` (INSERT OR IGNORE to handle duplicate order_id)
      - Generate license key via `keygen.GenerateLicenseKey()`
      - Store license in `si_licenses` (max_activations = 3)
      - Send license email via SMTP (with retry: 3 attempts, 5-second backoff)
      - Update webhook log status
   c. If `event_name == "order_refunded"`:
      - Find license by order_id
      - Set license status to "refunded"
      - Deactivate all active activations
      - Log in webhook_logs

---

## 8. Configuration (New env vars for Drolosoft)

Add to `internal/config/config.go`:

```go
// SoundInbox licensing
SoundInboxDBPath               string // "data/drolosoft.db"
SoundInboxWebhookSecret        string // HMAC secret from Lemon Squeezy
SoundInboxProductID            string // Lemon Squeezy product ID
SoundInboxVariantID            string // Lemon Squeezy variant ID  
SoundInboxMaxActivations       int    // Default: 3
SoundInboxSMTPHost             string // "smtp.sendgrid.net"
SoundInboxSMTPPort             int    // 587
SoundInboxSMTPUser             string // "apikey"
SoundInboxSMTPPass             string // SendGrid API key
SoundInboxSMTPFromName         string // "SoundInbox"
SoundInboxSMTPFromEmail        string // "hello@drolosoft.com"
SoundInboxSupportEmail         string // "support@drolosoft.com"
SoundInboxDownloadURL          string // "https://drolosoft.com/soundinbox/download"
SoundInboxActivationURL        string // "https://drolosoft.com/soundinbox/download#activation"
SoundInboxAdminUser            string // Admin basic auth username
SoundInboxAdminPass            string // Admin basic auth password
SoundInboxLemonSqueezyCheckoutURL string // "https://drolosoft.lemonsqueezy.com/buy/..."
```

`.env.example`:
```
# SoundInbox Licensing
SOUNDINBOX_DB_PATH=data/drolosoft.db
SOUNDINBOX_WEBHOOK_SECRET=your_webhook_secret_here
SOUNDINBOX_PRODUCT_ID=your_product_id
SOUNDINBOX_VARIANT_ID=your_variant_id
SOUNDINBOX_MAX_ACTIVATIONS=3
SOUNDINBOX_SMTP_HOST=smtp.sendgrid.net
SOUNDINBOX_SMTP_PORT=587
SOUNDINBOX_SMTP_USER=apikey
SOUNDINBOX_SMTP_PASS=your_sendgrid_api_key
SOUNDINBOX_SMTP_FROM_NAME=SoundInbox
SOUNDINBOX_SMTP_FROM_EMAIL=hello@drolosoft.com
SOUNDINBOX_SUPPORT_EMAIL=support@drolosoft.com
SOUNDINBOX_DOWNLOAD_URL=https://drolosoft.com/soundinbox/download
SOUNDINBOX_ACTIVATION_URL=https://drolosoft.com/soundinbox/download#activation
SOUNDINBOX_ADMIN_USER=admin
SOUNDINBOX_ADMIN_PASS=secure_password_here
SOUNDINBOX_LEMONSQUEEZY_CHECKOUT=https://drolosoft.lemonsqueezy.com/buy/soundinbox-pro
```

---

## 9. Web Pages

### 9.1 `/soundinbox.html` — Landing Page (already exists)

Already registered in `siteRegistry` as index 6 with template `products/soundinbox`. Currently behind `isAppsVisible()` gate. This page is the product overview — no changes to its existence needed, but it should include a CTA linking to pricing.

### 9.2 `/soundinbox/pricing` — Pricing Page

**Template:** `web/templates/site/pages/soundinbox/pricing.html`
**ExtraCSS:** `/css/product.css` (reuse existing product page styles)
**Structure:**

```
+--------------------------------------------------+
| Nav (standard Drolosoft nav)                      |
+--------------------------------------------------+
| Hero: "SoundInbox Pricing"                       |
| Subtitle: "Powerful email alerts. Free forever.  |
|   Pro when you need it."                         |
+--------------------------------------------------+
| Two-column pricing cards:                         |
|                                                  |
| +-------------------+  +---------------------+   |
| | FREE              |  | PRO — $14.99        |   |
| | (forever)         |  | (one-time)          |   |
| |                   |  |                     |   |
| | Everything:       |  | Everything in Free  |   |
| | - All 9 formulas  |  | PLUS:               |   |
| | - Custom rules    |  | - Up to 5 email     |   |
| | - Regex matching  |  |   accounts          |   |
| | - Custom sounds   |  |                     |   |
| | - Speech phrases  |  | Perfect for:        |   |
| | - DND schedules   |  | - Work + personal   |   |
| |                   |  | - Multiple clients  |   |
| | 1 email account   |  | - Team inboxes      |   |
| |                   |  |                     |   |
| | "Free isn't a     |  | [Buy Now — $14.99]  |   |
| |  trial. It's the  |  | (Download free      |   |
| |  real thing.      |  |  first, upgrade     |   |
| |  Every formula.   |  |  anytime)           |   |
| |  Every sound.     |  |                     |   |
| |  Unlimited rules. |  |                     |   |
| |  One inbox."      |  |                     |   |
| |                   |  |                     |   |
| | [Download Free]   |  |                     |   |
| +-------------------+  +---------------------+   |
+--------------------------------------------------+
| FAQ section (accordion):                          |
| - How do I activate my license?                  |
| - Can I use it on multiple Macs?                 |
| - What if I need a refund?                       |
| - Is it a subscription?                          |
| - Do I need to be online to use SoundInbox?      |
| - What happens if I don't upgrade?               |
| - Can I transfer my license to a new Mac?        |
| - Does it work with Outlook/IMAP?                |
+--------------------------------------------------+
| Footer (standard Drolosoft footer)               |
+--------------------------------------------------+
```

The "Buy Now" button links to the Lemon Squeezy checkout URL (env variable `SOUNDINBOX_LEMONSQUEEZY_CHECKOUT`).

### 9.3 `/soundinbox/download` — Download Page

**Template:** `web/templates/site/pages/soundinbox/download.html`
**Structure:**

```
+--------------------------------------------------+
| Nav                                              |
+--------------------------------------------------+
| Hero: "Download SoundInbox"                      |
| macOS 14+ required | Apple Silicon + Intel       |
+--------------------------------------------------+
| Two install methods:                              |
|                                                  |
| +-- Homebrew (recommended) --+                   |
| | brew install --cask soundinbox |               |
| +----------------------------+                   |
|                                                  |
| +-- Direct Download ---------+                   |
| | [Download DMG v1.0.0]      |                   |
| | SHA-256: abc123...          |                   |
| +----------------------------+                   |
+--------------------------------------------------+
| Activation instructions (anchor #activation):    |
| 1. Open SoundInbox from menu bar                |
| 2. Go to Settings > License                      |
| 3. Enter your license key                        |
| 4. Click "Activate"                              |
+--------------------------------------------------+
| Footer                                           |
+--------------------------------------------------+
```

**Post-purchase state (`?purchased=true`):**
When the download page is loaded with `?purchased=true` query parameter (redirect from Lemon Squeezy after purchase):
1. Show a success banner at the top: "Thank you for purchasing SoundInbox Pro! Your license key is on its way."
2. Display a prominent "Check your email" callout: "Your license key will arrive within 60 seconds at the email you used for purchase."
3. The activation instructions (#activation section) should be expanded by default.
4. Add a hint: "Already have SoundInbox installed? Open Settings > License and enter your key when it arrives."

### 9.4 `/soundinbox/privacy` — Privacy Policy (Google OAuth requirement)

**Template:** `web/templates/site/pages/soundinbox/privacy.html`

This page is **mandatory** for Google OAuth verification. It must specifically cover:

1. **What data SoundInbox accesses:** Gmail metadata only (sender, subject, snippet). No email body content is stored or transmitted.
2. **How data is used:** Local pattern matching only. No data leaves the device.
3. **Data storage:** All credentials stored in macOS Keychain. No cloud storage.
4. **Third-party sharing:** None. Zero. SoundInbox never transmits email content anywhere.
5. **Data retention:** Match history stored locally, user can clear anytime.
6. **User rights:** Users can revoke access via Google Account settings at any time.
7. **Contact:** support@drolosoft.com

Must include:
- Google API Services User Data Policy compliance statement
- Limited Use disclosure
- Last updated date
- Link from the app's OAuth consent screen

### 9.5 `/soundinbox/changelog` — Version History

Simple chronological list of versions and changes. Can be driven by a static data file or hardcoded struct in Go.

---

## 10. macOS Client Integration

### 10.1 New Swift Files

```
SoundInbox/
  Services/
    LicenseAPIService.swift     (network layer to talk to API)
    LicenseManager.swift        (state management, offline logic)
    DeviceIDService.swift       (stable device identifier)
  Models/
    LicenseState.swift          (Pro/Free enum, feature entitlements)
    LicenseResponse.swift       (Codable API response models)
  Views/
    LicenseSettingsView.swift   (settings tab for license management)
    UpgradePromptView.swift     (shown when hitting free limits)
    DeviceLimitView.swift       (shown when 3/3 devices used)
    ActivationSuccessView.swift (confirmation after activation)
```

### 10.2 DeviceIDService

Generates a stable, privacy-respecting device identifier:

```swift
struct DeviceIDService: Sendable {
    /// Returns a stable device identifier persisted in Keychain.
    /// Uses a UUID generated once and stored permanently.
    /// Does NOT use hardware serial or IOPlatformUUID (privacy concern).
    
    private static let serviceName = "com.soundinbox.system"
    private static let deviceIDKey = "device-id"
    
    static func getDeviceID() -> String {
        // Use dedicated Keychain service for system-level identifiers
        // NOT the per-account KeychainService (avoids namespace collision)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: deviceIDKey,
            kSecReturnData as String: true
        ]
        var result: AnyObject?
        if SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
           let data = result as? Data,
           let id = String(data: data, encoding: .utf8) {
            return id
        }
        let newID = UUID().uuidString
        let addQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: deviceIDKey,
            kSecValueData as String: newID.data(using: .utf8)!,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock
        ]
        SecItemAdd(addQuery as CFDictionary, nil)
        return newID
    }
    
    /// Returns the user-facing device name (e.g., "Juan's MacBook Pro")
    static var deviceName: String {
        ProcessInfo.processInfo.hostName  // Host.current().localizedName is deprecated in macOS 14+
    }
    
    /// Returns model identifier (e.g., "MacBookPro18,1")
    static var deviceModel: String {
        var size = 0
        sysctlbyname("hw.model", nil, &size, nil, 0)
        var model = [CChar](repeating: 0, count: size)
        sysctlbyname("hw.model", &model, &size, nil, 0)
        return String(cString: model)
    }
}
```

**Note:** DeviceIDService uses its own Keychain service (`com.soundinbox.system`) separate from the per-account `KeychainService` to avoid namespace collisions. License keys use service `com.soundinbox.license`.

### 10.3 LicenseState

```swift
enum LicenseTier: String, Codable, Sendable {
    case free
    case pro
}

struct FeatureEntitlements: Codable, Sendable {
    let maxAccounts: Int
    
    static let free = FeatureEntitlements(maxAccounts: 1)
    static let pro = FeatureEntitlements(maxAccounts: 5)
}

@Observable
final class LicenseManager {
    var tier: LicenseTier = .free
    var licenseKey: String?
    var entitlements: FeatureEntitlements = .free
    var lastVerified: Date?
    var isActivated: Bool { tier == .pro }
    
    // Offline grace period state
    var lastServerContact: Date?
    var graceDeadline: Date?  // 30 days after last successful verify
}
```

### 10.4 LicenseAPIService

```swift
actor LicenseAPIService {
    private let baseURL = "https://drolosoft.com/api/soundinbox"
    private let session: URLSession
    
    init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 15
        config.timeoutIntervalForResource = 30
        self.session = URLSession(configuration: config)
    }
    
    func validate(licenseKey: String) async throws -> ValidationResponse { ... }
    func activate(licenseKey: String) async throws -> ActivationResponse { ... }
    func deactivate(licenseKey: String, deviceID: String) async throws -> DeactivationResponse { ... }
    func getLicenseInfo(key: String) async throws -> LicenseInfoResponse { ... }
}
```

### 10.5 Offline Grace Period

The app must work offline. Verification schedule:

| Scenario | Behavior |
|----------|----------|
| **Every 7 days** | Attempt background validation (silent, no UI) |
| **Validation succeeds** | Update `lastServerContact`, reset grace period |
| **Validation fails (network)** | No change, will retry in 7 days |
| **30 days since last success** | Show warning: "Please connect to verify your license" |
| **90 days since last success** | Revert to free tier. Show: "License verification required. Connect to restore Pro features." |
| **User goes online + verifies** | Instantly restore Pro features, no data loss |
| **Refunded** | Verification returns status "refunded" | Immediately revert to free tier. Show message: "Your license has been refunded. Pro features have been deactivated." Clear license key from Keychain. |

**Clock manipulation protection:** The validate API response includes a `server_time` field (ISO 8601). The client stores this as `lastServerContact` instead of using `Date()`. On each verification check, if the stored `lastServerContact` is in the future relative to the current system clock, treat it as suspicious and use the earlier of (system time, stored time) for grace period calculations.

**Account pausing on revert to free:** When reverting from Pro to Free (offline expiry or refund), the app retains all configured accounts but pauses accounts 2-5. Paused accounts stop polling but retain their configuration, formulas, and history. A visual indicator (dimmed row, "Paused" badge) marks paused accounts. The oldest/first-configured account remains active. When Pro is restored, all accounts automatically resume. Extra accounts are NEVER deleted.

**Storage:** License key, tier, entitlements, lastServerContact, and graceDeadline are stored in the Keychain (sensitive) with a UserDefaults mirror for the non-secret entitlements (so the app can check limits without Keychain access on every operation).

### 10.6 Keychain Backend Migration

The app currently uses `useFileVault = true` in `KeychainService` for development (file-based credential storage). Before release, this must be flipped to `false` (real Keychain). Migration logic is required for beta testers:

1. On first launch after the switch, check if FileVault entries exist for any account
2. If found, migrate each credential (OAuth tokens, license key, device ID) to the real Keychain
3. Delete FileVault entries after successful migration
4. Log migration results for debugging

**This is critical for license keys:** A beta user who activates Pro via the FileVault backend and then updates to the Keychain backend would lose their license key without migration.

### 10.7 License Activation Flow (UX)

```
User opens Settings > License tab
  |
  v
[Enter License Key field]  [Activate button]
  |
  v (on tap Activate)
  |
  +-- Validate format locally (XXXXX-XXXXX-XXXXX-XXXXX-XXXXX)
  |     Fail? Show inline error: "Invalid format"
  |
  +-- Call POST /api/soundinbox/licenses/activate
  |     |
  |     +-- 201 Created: Show success animation, update tier to .pro
  |     |
  |     +-- 200 OK (already activated): Show "Already active on this device"
  |     |
  |     +-- 403 (limit reached): Show DeviceLimitView with device list
  |     |     User can deactivate a device from the list, then retry
  |     |
  |     +-- 404 (not found): Show "License key not found"
  |     |
  |     +-- Network error: Show "Could not connect. Try again later."
```

### 10.8 Upgrade Prompt Trigger Points

The UpgradePromptView appears when:
1. User tries to add a 2nd email account (the only free-tier limit)

The prompt shows:
- "Add more email accounts with SoundInbox Pro"
- "Monitor work, personal, and client inboxes — all with their own formulas"
- "Upgrade for $14.99 (one-time)" button (links to Lemon Squeezy checkout)
- "I already have a key" link (opens license settings)

---

## 11. Email Templates

### 11.1 License Delivery Email

Subject: `Your SoundInbox Pro License Key`

Branded for SoundInbox (orange/amber theme matching the app icon), otherwise identical structure to Commando's email:
- Welcome message with customer name
- License key in prominent box
- Download button (links to `/soundinbox/download`)
- Activation instructions button
- Order details table (order ID, date, amount)
- Quick start guide (4 steps)
- Support info
- Footer: "Use on up to 3 devices"

### 11.2 Email Service Configuration

Reuse the same SendGrid account as Commando. Different "From" name:
- From: `SoundInbox <hello@drolosoft.com>`
- Reply-To: `support@drolosoft.com`

### 11.3 Email Delivery Reliability

- **Retry logic:** On SMTP failure, retry up to 3 times with 5-second exponential backoff.
- **Admin resend:** The license detail page (`/admin/soundinbox/licenses/{key}`) includes a "Resend Email" button for manual retry.
- **Periodic sweep:** Every 10 minutes, query for licenses where `email_sent = 0 AND email_error IS NOT NULL AND created_at > datetime('now', '-1 hour')` and retry delivery.
- **Monitoring:** The admin dashboard shows a count of unsent emails as an alert indicator.

---

## 12. Security

### 12.1 Middleware

| Middleware | Applies To | Behavior |
|------------|-----------|----------|
| Rate Limit (60/min) | `/api/soundinbox/licenses/*` | IP-based, token bucket |
| Rate Limit (100/min) | `/api/soundinbox/webhooks/*` | IP-based |
| CORS | `/api/soundinbox/*` | Allow only: `https://drolosoft.com`, macOS app (no origin) |
| Security Headers | All routes | X-Content-Type-Options, X-Frame-Options, etc. |
| Basic Auth | `/admin/soundinbox/*` | Username/password from env |

### 12.2 Webhook Security

- HMAC-SHA256 signature verification (constant-time comparison)
- Reject missing/empty `X-Signature` header with HTTP 401. Do NOT return error details (e.g., "invalid signature") — return a generic 401 with no body to avoid confirming endpoint existence to attackers.
- Respond 200 before async processing (prevent timeout retries)
- Log all webhook attempts (successful and failed)

### 12.3 License Key Security

- Generated with `crypto/rand` (not `math/rand`)
- Stored hashed? No — keys must be recoverable for email resend. Store plaintext in DB.
- Keys transmitted over HTTPS only
- Keys stored in macOS Keychain on client (not UserDefaults)

### 12.4 Admin Security

- Basic Auth over HTTPS
- Credentials from environment variables (never hardcoded)
- Password comparison MUST use `crypto/subtle.ConstantTimeCompare` to prevent timing attacks. Consider storing the admin password hashed (bcrypt) in the environment variable.
- Admin routes not indexed (robots.txt disallow)
- No admin JS — server-rendered HTML only

### 12.5 Activation Race Condition

**Activation race condition:** Use atomic SQL for activation count: `UPDATE si_licenses SET current_activations = current_activations + 1 WHERE license_key = ? AND current_activations < max_activations`. Check affected rows count — if 0, the limit was reached. This prevents two simultaneous requests from both passing the limit check.

---

## 13. Lemon Squeezy Setup

### 13.1 Product Configuration

Create in Lemon Squeezy dashboard:

| Field | Value |
|-------|-------|
| Product name | SoundInbox Pro |
| Price | $14.99 (one-time) |
| Tax category | Software |
| Description | Unlock unlimited formulas, custom rules, regex matching, multiple accounts, custom sounds, and speech alerts |

### 13.2 Variant

Single variant: "SoundInbox Pro License" — one-time payment, no subscription.

### 13.3 Webhook Configuration

| Setting | Value |
|---------|-------|
| URL | `https://drolosoft.com/api/soundinbox/webhooks/lemonsqueezy` |
| Secret | (generate and store in env) |
| Events | `order_created`, `order_refunded` |

### 13.4 Checkout Customization

- Thank you page redirect: `https://drolosoft.com/soundinbox/download?purchased=true`
- Custom fields: none needed (email is captured by Lemon Squeezy)

---

## 14. Deployment Notes

### 14.1 Changes to Existing Server

The Drolosoft server (`/Users/txeo/Git/mac/go/drolosoft/`) must be extended:

1. **Add `database/sql` and SQLite driver** to `go.mod`:
   ```
   github.com/mattn/go-sqlite3
   ```

2. **Add new route registrations** in `cmd/server/main.go`:
   ```go
   // SoundInbox pages
   mux.HandleFunc("/soundinbox/pricing", soundinboxHandler.Pricing)
   mux.HandleFunc("/soundinbox/download", soundinboxHandler.Download)
   mux.HandleFunc("/soundinbox/privacy", soundinboxHandler.Privacy)
   mux.HandleFunc("/soundinbox/changelog", soundinboxHandler.Changelog)
   
   // SoundInbox License API
   mux.HandleFunc("/api/soundinbox/licenses/validate", rateLimited(soundinboxAPI.ValidateLicense))
   mux.HandleFunc("/api/soundinbox/licenses/activate", rateLimited(soundinboxAPI.ActivateLicense))
   mux.HandleFunc("/api/soundinbox/licenses/deactivate", rateLimited(soundinboxAPI.DeactivateLicense))
   mux.HandleFunc("/api/soundinbox/licenses/", rateLimited(soundinboxAPI.GetLicense))
   mux.HandleFunc("/api/soundinbox/webhooks/lemonsqueezy", webhookLimited(soundinboxAPI.WebhookHandler))
   mux.HandleFunc("/api/soundinbox/health", soundinboxAPI.HealthCheck)
   
   // SoundInbox Admin (protected)
   mux.Handle("/admin/soundinbox/", basicAuth(soundinboxAdmin))
   ```

3. **Create `data/` directory** for SQLite database (auto-created on first run)

4. **Run migrations on startup** (embedded SQL, like Commando)

5. **Add health check** that includes DB connectivity for monitoring

### 14.2 Deployment Checklist

- [ ] Lemon Squeezy product created, webhook configured
- [ ] Environment variables set on production server
- [ ] SQLite database file path writable
- [ ] SendGrid API key configured
- [ ] SSL/TLS certificate covers drolosoft.com (already does)
- [ ] robots.txt updated to disallow `/admin/`
- [ ] Google OAuth consent screen updated with privacy policy URL
- [ ] Test webhook with Lemon Squeezy's test mode
- [ ] Test full flow: purchase > webhook > email > activate > validate

### 14.3 Monitoring

- Log all webhook events (success and failure)
- Log all license operations (activate, deactivate, validate)
- Health endpoint at `/api/soundinbox/health` returns DB status
- Admin dashboard shows: total licenses, active licenses, unprocessed orders, failed webhooks

### 14.4 SQLite Notes

- **CGO dependency:** `mattn/go-sqlite3` requires CGO enabled, which complicates cross-compilation. Consider `modernc.org/sqlite` as a pure-Go alternative. Document the chosen driver.
- **Backup strategy:** Schedule periodic file-level copies of `data/drolosoft.db` (e.g., hourly cron to `data/backups/`). SQLite's online backup API can be used for zero-downtime copies. Keep 7 days of backups.

---

## 15. Google OAuth Privacy Policy Requirements

Google's OAuth verification process requires:

1. **Privacy policy URL** submitted during OAuth consent screen setup: `https://drolosoft.com/soundinbox/privacy`
2. **Limited Use compliance** — the privacy page must explicitly state adherence to Google API Services User Data Policy
3. **Scope justification** — SoundInbox uses `https://mail.google.com/` scope for IMAP access. The privacy policy must explain why (pattern matching on email headers only, no content storage)
4. **Homepage URL** — `https://drolosoft.com/soundinbox.html`
5. **Terms of Service URL** — `https://drolosoft.com/legal/terms.html` (existing)

The privacy page at `/soundinbox/privacy` is the critical deliverable for OAuth verification approval.

---

## 16. Implementation Order (Suggested)

1. **Phase 1 — Backend foundation + Privacy page:**
   - Add SQLite to Drolosoft Go app
   - Port `internal/licensing` package (keygen, models, repository, migrations)
   - Add config fields and env parsing
   - Run migrations on startup
   - **Create privacy policy page** (`/soundinbox/privacy`) — this is a blocker for Google OAuth verification and cannot be deferred

2. **Phase 2 — API endpoints:**
   - Implement validate, activate, deactivate, get license handlers
   - Implement webhook handler
   - Add rate limiting middleware
   - Test with curl

3. **Phase 3 — Email delivery:**
   - Port email service from Commando
   - Create SoundInbox-branded HTML template
   - Test email delivery via SendGrid

4. **Phase 4 — Web pages:**
   - Create pricing page template
   - Create download page template
   - Create changelog page
   - Add routes to main.go

5. **Phase 5 — Admin panel:**
   - Basic auth middleware
   - Dashboard with stats
   - License list/detail/revoke
   - Manual license generation
   - Webhook logs viewer

6. **Phase 6 — macOS client:**
   - Add DeviceIDService
   - Add LicenseAPIService
   - Add LicenseManager with offline logic
   - Add LicenseState + FeatureEntitlements
   - Add LicenseSettingsView
   - Add UpgradePromptView
   - Wire feature gates into FormulaStore

7. **Phase 7 — Lemon Squeezy:**
   - Create product in dashboard
   - Configure webhook
   - Test end-to-end with test mode
   - Go live

---

## 17. Open Decisions (Resolved)

| Question | Decision | Rationale |
|----------|----------|-----------|
| Separate DB or shared? | Single `drolosoft.db` with table prefixes | Simpler deployment, one backup target |
| Max activations? | 3 devices | Generous enough for laptop + desktop + spare; Commando uses 2 but SoundInbox is cheaper |
| Subscription or one-time? | One-time $14.99 | Matches the product's value prop — set it and forget it. No ongoing service cost. |
| License key delivery method? | Email (immediate, via SMTP) | Standard approach, proven in Commando |
| Offline policy? | 7-day check, 30-day warning, 90-day revert | Generous. Most users connect weekly. Protects against piracy. |
| What's the paywall? | Email account limit (Free=1, Pro=5) | Full product for free, pay only when you need multiple accounts. Simple, fair, no feature crippling. |
| Feature gates enforced where? | Client-side (Swift) using server-provided entitlements | API returns `max_accounts` on validate/activate. Client caches and enforces. No per-action API calls. |
| Admin panel tech? | Server-rendered HTML (Go templates) | Matches Drolosoft/Commando pattern. No JS framework needed. |
| CORS policy? | Allow drolosoft.com + no-origin (native apps) | Desktop apps don't send Origin header. Only browser needs CORS. |
