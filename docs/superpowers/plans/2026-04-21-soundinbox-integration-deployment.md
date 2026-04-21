# SoundInbox Integration, Testing & Deployment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up Lemon Squeezy payment provider, deploy the Go backend to production, run comprehensive E2E tests across the full purchase→webhook→email→activate→validate flow, and go live.

**Architecture:** This plan assumes the Go backend (Plan 1) and macOS client (Plan 2) are already built. It connects them through Lemon Squeezy payment integration, deploys to the production drolosoft.com server, and validates the complete user journey end-to-end.

**Tech Stack:** Lemon Squeezy (payment), SendGrid (email), Nginx (reverse proxy), systemd (process management), curl (testing), Go binary deployment.

**Prerequisites:** 
- Backend plan completed and passing all tests locally
- macOS client plan completed and building successfully  
- Access to: Lemon Squeezy dashboard, SendGrid account, drolosoft.com server (SSH), Google OAuth console

---

## Task 1: Lemon Squeezy Product Setup

**What:** Configure the SoundInbox Pro product, variant, webhook, and checkout in the Lemon Squeezy dashboard. Record all IDs needed for production environment variables.

**Why:** This is the payment provider that handles the entire purchase flow. Without it, there is no way to accept payments or trigger license creation.

### Steps

- [ ] **1.1** Log in to Lemon Squeezy dashboard at https://app.lemonsqueezy.com
  - Use the existing Drolosoft store account

- [ ] **1.2** Create the product:
  - Navigate to: **Store > Products > + New Product**
  - Fill in the following fields:

  | Field | Value |
  |-------|-------|
  | Product name | `SoundInbox Pro` |
  | Description | `Unlock up to 5 email accounts in SoundInbox. All features are unlimited — Pro gives you multi-account monitoring for work, personal, and client inboxes. One payment, yours forever.` |
  | Status | `Published` |
  | Tax category | `Software` |
  | Media | Upload SoundInbox icon (orange/amber app icon, 512x512 PNG) |

- [ ] **1.3** Create the variant:
  - In the product editor, go to the **Pricing** section
  - Configure:

  | Field | Value |
  |-------|-------|
  | Variant name | `SoundInbox Pro License` |
  | Payment type | `One-time payment` (NOT subscription) |
  | Price | `$14.99 USD` |
  | Trial period | None |
  | Subscription | None |

- [ ] **1.4** Configure checkout customization:
  - In the product editor, go to **Checkout** section
  - Set:

  | Field | Value |
  |-------|-------|
  | Thank you page redirect | `https://drolosoft.com/soundinbox/download?purchased=true` |
  | Custom confirmation message | `Your license key will arrive by email within 60 seconds.` |
  | Logo | SoundInbox icon (orange/amber) |
  | Button color | `#F59E0B` (amber-500, matching SoundInbox brand) |

- [ ] **1.5** Configure the webhook:
  - Navigate to: **Settings > Webhooks > + Add Endpoint**
  - Fill in:

  | Field | Value |
  |-------|-------|
  | Webhook URL | `https://drolosoft.com/api/soundinbox/webhooks/lemonsqueezy` |
  | Signing secret | Generate with: `openssl rand -hex 32` |
  | Events | Check ONLY: `order_created`, `order_refunded` |

  Generate the signing secret locally:
  ```bash
  openssl rand -hex 32
  # Example output: a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcdef01
  # Save this — it goes into SOUNDINBOX_WEBHOOK_SECRET
  ```

- [ ] **1.6** Record all values — you will need these for Task 4:
  ```
  SOUNDINBOX_PRODUCT_ID=<copy from product URL: /products/{id}>
  SOUNDINBOX_VARIANT_ID=<copy from variant settings or API>
  SOUNDINBOX_WEBHOOK_SECRET=<the signing secret from step 1.5>
  SOUNDINBOX_LEMONSQUEEZY_CHECKOUT=https://drolosoft.lemonsqueezy.com/buy/<variant-uuid>
  ```

  To find the checkout URL: Go to the product page, click **Share**, copy the direct checkout link. It will look like `https://drolosoft.lemonsqueezy.com/buy/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`.

- [ ] **1.7** Verify the product is visible in your Lemon Squeezy store by opening the checkout URL in a browser. You should see the SoundInbox Pro purchase page with the correct price ($14.99), description, and branding.

### Acceptance Criteria

- Product "SoundInbox Pro" exists in Lemon Squeezy with $14.99 one-time pricing
- Webhook endpoint configured with correct URL and events
- Checkout URL opens a working purchase page in browser
- All four values (product_id, variant_id, webhook_secret, checkout_url) are recorded

---

## Task 2: SendGrid Email Configuration

**What:** Configure SendGrid to send license delivery emails from `hello@drolosoft.com` with proper DNS authentication so emails reach the inbox (not spam).

**Why:** After a purchase, the license key is delivered via email. Without verified DNS records, emails land in spam or get rejected entirely.

### Steps

- [ ] **2.1** Log in to SendGrid at https://app.sendgrid.com
  - Use the existing Drolosoft/Commando account, or create a new one if none exists

- [ ] **2.2** Verify the sender identity:
  - Navigate to: **Settings > Sender Authentication > Verify a Single Sender**
  - Or if using domain authentication (preferred): **Settings > Sender Authentication > Authenticate Your Domain**
  - For single sender verification:

  | Field | Value |
  |-------|-------|
  | From Name | `SoundInbox` |
  | From Email | `hello@drolosoft.com` |
  | Reply To | `support@drolosoft.com` |
  | Company | `Drolosoft` |
  | Address | (your business address) |

  - Check inbox for `hello@drolosoft.com` and click the verification link

- [ ] **2.3** Set up domain authentication (if not already done for drolosoft.com):
  - Navigate to: **Settings > Sender Authentication > Domain Authentication**
  - Select DNS host (e.g., Cloudflare, Namecheap, etc.)
  - Enter domain: `drolosoft.com`
  - SendGrid will generate three DNS records. Add them to your DNS provider:

  **SPF record** (TXT on drolosoft.com):
  ```
  v=spf1 include:sendgrid.net ~all
  ```
  If an SPF record already exists, append `include:sendgrid.net` before the `~all`.

  **DKIM records** (CNAME — SendGrid will provide exact values):
  ```
  s1._domainkey.drolosoft.com → s1.domainkey.uXXXXXX.wlXXX.sendgrid.net
  s2._domainkey.drolosoft.com → s2.domainkey.uXXXXXX.wlXXX.sendgrid.net
  ```

  **DMARC record** (TXT on `_dmarc.drolosoft.com`):
  ```
  v=DMARC1; p=quarantine; rua=mailto:dmarc@drolosoft.com; pct=100
  ```

- [ ] **2.4** Verify DNS propagation:
  ```bash
  # Check SPF
  dig TXT drolosoft.com +short
  # Should include: "v=spf1 include:sendgrid.net ~all"

  # Check DKIM
  dig CNAME s1._domainkey.drolosoft.com +short
  # Should return SendGrid CNAME target

  # Check DMARC
  dig TXT _dmarc.drolosoft.com +short
  # Should return: "v=DMARC1; p=quarantine; ..."
  ```
  DNS propagation can take up to 48 hours. Proceed with other tasks while waiting.

- [ ] **2.5** Create a restricted API key:
  - Navigate to: **Settings > API Keys > Create API Key**
  - Name: `SoundInbox License Delivery`
  - Permissions: **Restricted Access**
    - Enable ONLY: **Mail Send > Full Access**
    - All other permissions: **No Access**
  - Click **Create & View**
  - Copy the key immediately (it starts with `SG.` and is only shown once)

- [ ] **2.6** Test email delivery:
  ```bash
  curl -X POST https://api.sendgrid.com/v3/mail/send \
    -H "Authorization: Bearer SG.YOUR_API_KEY_HERE" \
    -H "Content-Type: application/json" \
    -d '{
      "personalizations": [{"to": [{"email": "txeo.msx@gmail.com"}]}],
      "from": {"email": "hello@drolosoft.com", "name": "SoundInbox"},
      "subject": "SoundInbox SendGrid Test",
      "content": [{"type": "text/plain", "value": "If you receive this, SendGrid is working for SoundInbox."}]
    }'
  ```
  Expected: HTTP 202 Accepted. Check inbox (and spam folder) within 2 minutes.

- [ ] **2.7** Record SMTP credentials for Task 4:
  ```
  SOUNDINBOX_SMTP_HOST=smtp.sendgrid.net
  SOUNDINBOX_SMTP_PORT=587
  SOUNDINBOX_SMTP_USER=apikey
  SOUNDINBOX_SMTP_PASS=SG.<your_api_key_from_step_2.5>
  SOUNDINBOX_SMTP_FROM_NAME=SoundInbox
  SOUNDINBOX_SMTP_FROM_EMAIL=hello@drolosoft.com
  ```

### Acceptance Criteria

- Sender `hello@drolosoft.com` is verified in SendGrid
- SPF, DKIM, and DMARC DNS records are configured for drolosoft.com
- API key with Mail Send permission is created
- Test email arrives in inbox (not spam) at a personal address
- SMTP credentials are recorded

---

## Task 3: Google OAuth Console Update

**What:** Update the Google OAuth consent screen with production URLs so that SoundInbox can proceed with OAuth verification for publishing beyond test users.

**Why:** Google requires a working privacy policy URL and homepage URL on the consent screen before verifying the app. Without verification, only test users can authenticate.

### Steps

- [ ] **3.1** Open Google Cloud Console:
  - URL: https://console.cloud.google.com
  - Select the SoundInbox project (Client ID: `77176507159-e9e6631v3bcs0g1m98teq128tfr24ifi`)

- [ ] **3.2** Navigate to: **APIs & Services > OAuth consent screen**

- [ ] **3.3** Update the consent screen fields:

  | Field | Value |
  |-------|-------|
  | App name | `SoundInbox` |
  | User support email | `support@drolosoft.com` |
  | App homepage | `https://drolosoft.com/soundinbox.html` |
  | Application privacy policy link | `https://drolosoft.com/soundinbox/privacy` |
  | Application terms of service link | `https://drolosoft.com/legal/terms.html` |
  | Developer contact email | `support@drolosoft.com` |

- [ ] **3.4** Verify the privacy page is accessible:
  ```bash
  curl -s -o /dev/null -w "%{http_code}" https://drolosoft.com/soundinbox/privacy
  # Expected: 200
  ```
  If this returns 404, the backend has not been deployed yet. Deploy first (Task 5), then come back to verify.

- [ ] **3.5** Verify the privacy page contains required Google compliance elements:
  ```bash
  curl -s https://drolosoft.com/soundinbox/privacy | grep -c "Google API Services User Data Policy"
  # Expected: >= 1 (the compliance statement must appear on the page)
  
  curl -s https://drolosoft.com/soundinbox/privacy | grep -c "Limited Use"
  # Expected: >= 1 (Limited Use disclosure must appear)
  ```

- [ ] **3.6** Save the consent screen changes.

- [ ] **3.7** If the app is still in "Testing" status and you need to go beyond 100 test users, click **Publish App** and submit for verification. Note: Google verification can take 4-6 weeks. Plan accordingly.

### Acceptance Criteria

- OAuth consent screen shows correct homepage, privacy, and terms URLs
- Privacy page at `https://drolosoft.com/soundinbox/privacy` returns 200 and contains Google API Services User Data Policy compliance language
- Consent screen changes are saved

---

## Task 4: Create Production Environment File

**What:** Create the `.env.production` file containing all `SOUNDINBOX_*` variables needed by the Go backend, with documentation of where each value comes from.

**Why:** The production server needs every configuration value to be set correctly. A missing or wrong variable causes silent failures (no emails, webhook rejections, etc.). This file is the single source of truth.

### Steps

- [ ] **4.1** Generate secure secrets:
  ```bash
  # Webhook signing secret (if not already generated in Task 1)
  openssl rand -hex 32
  
  # Admin password (strong, random)
  openssl rand -base64 24
  ```

- [ ] **4.2** Create the production environment file at `/Users/txeo/Git/mac/go/drolosoft/.env.production`:
  ```env
  # =============================================================
  # SoundInbox Production Environment Variables
  # =============================================================
  # Created: 2026-04-21
  # Server: drolosoft.com
  # 
  # DO NOT COMMIT THIS FILE. It contains secrets.
  # Copy values to the systemd service file on the production server.
  # =============================================================

  # --- Database ---
  # Source: Local path on production server
  # The server creates this file automatically on first run
  SOUNDINBOX_DB_PATH=data/drolosoft.db

  # --- Lemon Squeezy ---
  # Source: Lemon Squeezy dashboard (Task 1)
  # Product URL: https://app.lemonsqueezy.com/products/<id>
  SOUNDINBOX_PRODUCT_ID=<from Task 1.6 — Lemon Squeezy product page URL>
  SOUNDINBOX_VARIANT_ID=<from Task 1.6 — Lemon Squeezy variant settings>
  SOUNDINBOX_WEBHOOK_SECRET=<from Task 1.5 — the openssl rand -hex 32 output>
  SOUNDINBOX_LEMONSQUEEZY_CHECKOUT=<from Task 1.6 — checkout URL>

  # --- License Defaults ---
  # Source: Spec Section 3 — 3 devices per license key
  SOUNDINBOX_MAX_ACTIVATIONS=3

  # --- SendGrid SMTP ---
  # Source: SendGrid dashboard (Task 2)
  SOUNDINBOX_SMTP_HOST=smtp.sendgrid.net
  SOUNDINBOX_SMTP_PORT=587
  SOUNDINBOX_SMTP_USER=apikey
  SOUNDINBOX_SMTP_PASS=<from Task 2.5 — starts with SG.>
  SOUNDINBOX_SMTP_FROM_NAME=SoundInbox
  SOUNDINBOX_SMTP_FROM_EMAIL=hello@drolosoft.com

  # --- Contact Info ---
  SOUNDINBOX_SUPPORT_EMAIL=support@drolosoft.com
  SOUNDINBOX_DOWNLOAD_URL=https://drolosoft.com/soundinbox/download
  SOUNDINBOX_ACTIVATION_URL=https://drolosoft.com/soundinbox/download#activation

  # --- Admin Panel ---
  # Source: Generated locally (Task 4.1)
  # CRITICAL: Change the default password before deploying
  SOUNDINBOX_ADMIN_USER=admin
  SOUNDINBOX_ADMIN_PASS=<from Task 4.1 — openssl rand -base64 24 output>
  ```

- [ ] **4.3** Verify `.env.production` is in `.gitignore`:
  ```bash
  cd /Users/txeo/Git/mac/go/drolosoft
  grep -q ".env.production" .gitignore || echo ".env.production" >> .gitignore
  ```

- [ ] **4.4** Fill in all placeholder values with actual values from Tasks 1 and 2. Every `<from Task ...>` placeholder must be replaced with a real value.

- [ ] **4.5** Validate the file has no remaining placeholders:
  ```bash
  grep -c "<from Task" /Users/txeo/Git/mac/go/drolosoft/.env.production
  # Expected: 0 (all placeholders replaced)
  ```

### Acceptance Criteria

- `.env.production` exists with all 17 `SOUNDINBOX_*` variables
- No placeholder values remain
- File is in `.gitignore`
- Webhook secret and admin password are cryptographically random

---

## Task 5: Deploy Go Backend to Production

**What:** Build the Go binary, upload it to the drolosoft.com production server, configure the systemd service with environment variables, and start the service.

**Why:** The backend must be running in production before any E2E testing or Lemon Squeezy webhook delivery can work.

### Steps

- [ ] **5.1** Build the Go binary locally:
  ```bash
  cd /Users/txeo/Git/mac/go/drolosoft
  
  # Build for Linux (production server architecture)
  GOOS=linux GOARCH=amd64 CGO_ENABLED=1 go build -o ./bin/server-linux-amd64 ./cmd/server
  
  # Verify the binary was created
  file ./bin/server-linux-amd64
  # Expected: ELF 64-bit LSB executable, x86-64
  ```

  **Note on CGO:** If using `mattn/go-sqlite3`, CGO is required and cross-compilation needs a cross-compiler (`x86_64-linux-musl-gcc` or similar). If using `modernc.org/sqlite` (pure Go), set `CGO_ENABLED=0` instead:
  ```bash
  # Alternative for pure-Go SQLite driver
  GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -o ./bin/server-linux-amd64 ./cmd/server
  ```

- [ ] **5.2** Create the data directory on the production server:
  ```bash
  ssh production "mkdir -p /opt/drolosoft/data/backups && chown -R drolosoft:drolosoft /opt/drolosoft/data"
  ```

- [ ] **5.3** Upload the binary to the server:
  ```bash
  scp ./bin/server-linux-amd64 production:/opt/drolosoft/server-new
  ssh production "chmod +x /opt/drolosoft/server-new"
  ```

- [ ] **5.4** Update the systemd service environment file on the server. SSH in and edit `/etc/systemd/system/drolosoft.service` (or the environment file it references):
  ```bash
  ssh production
  ```

  If the service uses an `EnvironmentFile`:
  ```bash
  sudo vi /etc/drolosoft/env
  # Add all SOUNDINBOX_* variables from .env.production
  ```

  If the service uses inline `Environment=` directives, add them to the `[Service]` section:
  ```ini
  [Service]
  # ... existing config ...
  
  # SoundInbox Licensing
  Environment=SOUNDINBOX_DB_PATH=data/drolosoft.db
  Environment=SOUNDINBOX_PRODUCT_ID=<actual value>
  Environment=SOUNDINBOX_VARIANT_ID=<actual value>
  Environment=SOUNDINBOX_WEBHOOK_SECRET=<actual value>
  Environment=SOUNDINBOX_LEMONSQUEEZY_CHECKOUT=<actual value>
  Environment=SOUNDINBOX_MAX_ACTIVATIONS=3
  Environment=SOUNDINBOX_SMTP_HOST=smtp.sendgrid.net
  Environment=SOUNDINBOX_SMTP_PORT=587
  Environment=SOUNDINBOX_SMTP_USER=apikey
  Environment=SOUNDINBOX_SMTP_PASS=<actual value>
  Environment=SOUNDINBOX_SMTP_FROM_NAME=SoundInbox
  Environment=SOUNDINBOX_SMTP_FROM_EMAIL=hello@drolosoft.com
  Environment=SOUNDINBOX_SUPPORT_EMAIL=support@drolosoft.com
  Environment=SOUNDINBOX_DOWNLOAD_URL=https://drolosoft.com/soundinbox/download
  Environment=SOUNDINBOX_ACTIVATION_URL=https://drolosoft.com/soundinbox/download#activation
  Environment=SOUNDINBOX_ADMIN_USER=admin
  Environment=SOUNDINBOX_ADMIN_PASS=<actual value>
  ```

- [ ] **5.5** Deploy the new binary with minimal downtime:
  ```bash
  ssh production "sudo systemctl stop drolosoft && \
    cp /opt/drolosoft/server /opt/drolosoft/server-backup-$(date +%Y%m%d%H%M%S) && \
    mv /opt/drolosoft/server-new /opt/drolosoft/server && \
    sudo systemctl daemon-reload && \
    sudo systemctl start drolosoft"
  ```

- [ ] **5.6** Verify the service is running:
  ```bash
  ssh production "sudo systemctl status drolosoft"
  # Expected: Active: active (running)
  
  ssh production "journalctl -u drolosoft -n 20 --no-pager"
  # Check for any startup errors, especially SQLite initialization and migration logs
  ```

- [ ] **5.7** Verify the health endpoint from your local machine:
  ```bash
  curl -s https://drolosoft.com/api/soundinbox/health | python3 -m json.tool
  ```
  Expected response:
  ```json
  {
      "status": "ok",
      "database": "connected",
      "version": "1.0.0"
  }
  ```

- [ ] **5.8** Update robots.txt on the server (if not handled by the Go app):
  ```bash
  ssh production "grep -q '/admin/' /opt/drolosoft/web/static/robots.txt || \
    echo -e '\nDisallow: /admin/' >> /opt/drolosoft/web/static/robots.txt"
  ```

  Verify:
  ```bash
  curl -s https://drolosoft.com/robots.txt | grep admin
  # Expected: Disallow: /admin/
  ```

### Acceptance Criteria

- Health endpoint returns `{"status":"ok","database":"connected",...}`
- Service is running without errors in `journalctl`
- SQLite database was created at `data/drolosoft.db`
- robots.txt disallows `/admin/`

---

## Task 6: Production Smoke Tests

**What:** Run a comprehensive suite of curl-based tests against the production API to verify every endpoint is responding correctly before any Lemon Squeezy integration testing.

**Why:** Catch deployment issues (missing env vars, misconfigured routes, broken middleware) before wiring up payments. Fixing these now prevents confusing failures during E2E testing.

### Steps

- [ ] **6.1** Test health endpoint:
  ```bash
  curl -s -w "\nHTTP Status: %{http_code}\n" https://drolosoft.com/api/soundinbox/health
  ```
  Expected:
  ```json
  {"status":"ok","database":"connected","version":"1.0.0"}
  HTTP Status: 200
  ```

- [ ] **6.2** Test validate with an invalid license key:
  ```bash
  curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/validate \
    -H "Content-Type: application/json" \
    -d '{"license_key":"AAAAA-BBBBB-CCCCC-DDDDD-EEEEE"}' \
    -w "\nHTTP Status: %{http_code}\n"
  ```
  Expected:
  ```json
  {"valid":false,"message":"License key not found","status":"not_found"}
  HTTP Status: 404
  ```

- [ ] **6.3** Test validate with a malformed key (bad format):
  ```bash
  curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/validate \
    -H "Content-Type: application/json" \
    -d '{"license_key":"not-a-valid-key"}' \
    -w "\nHTTP Status: %{http_code}\n"
  ```
  Expected:
  ```json
  {"valid":false,"message":"Invalid license key format"}
  HTTP Status: 400
  ```

- [ ] **6.4** Test activate with invalid key:
  ```bash
  curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/activate \
    -H "Content-Type: application/json" \
    -d '{
      "license_key":"AAAAA-BBBBB-CCCCC-DDDDD-EEEEE",
      "device_id":"TEST-001",
      "device_name":"Test Mac",
      "device_model":"MacBookPro18,1",
      "os_version":"15.2",
      "app_version":"1.0.0"
    }' \
    -w "\nHTTP Status: %{http_code}\n"
  ```
  Expected:
  ```json
  {"success":false,"message":"License key not found"}
  HTTP Status: 404
  ```

- [ ] **6.5** Test method rejection (GET on a POST-only endpoint):
  ```bash
  curl -s -X GET https://drolosoft.com/api/soundinbox/licenses/validate \
    -w "\nHTTP Status: %{http_code}\n"
  ```
  Expected:
  ```
  HTTP Status: 405
  ```

- [ ] **6.6** Test web pages:
  ```bash
  # Privacy page (critical for Google OAuth)
  curl -s -o /dev/null -w "Privacy: %{http_code}\n" https://drolosoft.com/soundinbox/privacy

  # Pricing page
  curl -s -o /dev/null -w "Pricing: %{http_code}\n" https://drolosoft.com/soundinbox/pricing

  # Download page
  curl -s -o /dev/null -w "Download: %{http_code}\n" https://drolosoft.com/soundinbox/download

  # Download page with purchase query param
  curl -s -o /dev/null -w "Download (purchased): %{http_code}\n" "https://drolosoft.com/soundinbox/download?purchased=true"
  ```
  Expected: All return `200`.

- [ ] **6.7** Test admin without credentials (should be rejected):
  ```bash
  curl -s -o /dev/null -w "Admin no-auth: %{http_code}\n" https://drolosoft.com/admin/soundinbox/
  ```
  Expected: `401`

- [ ] **6.8** Test admin with correct credentials:
  ```bash
  curl -s -o /dev/null -w "Admin with-auth: %{http_code}\n" \
    -u "admin:<SOUNDINBOX_ADMIN_PASS>" \
    https://drolosoft.com/admin/soundinbox/
  ```
  Expected: `200`

- [ ] **6.9** Test rate limiting (send 70 rapid requests to exceed 60/min limit):
  ```bash
  for i in $(seq 1 70); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
      https://drolosoft.com/api/soundinbox/licenses/validate \
      -H "Content-Type: application/json" \
      -d '{"license_key":"AAAAA-BBBBB-CCCCC-DDDDD-EEEEE"}')
    if [ "$STATUS" = "429" ]; then
      echo "Rate limited at request $i (HTTP 429) — PASS"
      break
    fi
  done
  ```
  Expected: Should see `429` before reaching request 70.

- [ ] **6.10** Test CORS (browser-origin request from unauthorized domain):
  ```bash
  curl -s -H "Origin: https://evil.com" \
    -X OPTIONS \
    -D - \
    https://drolosoft.com/api/soundinbox/licenses/validate 2>&1 | grep -i "access-control"
  ```
  Expected: No `Access-Control-Allow-Origin: https://evil.com` header. The request should either have no CORS headers or be explicitly blocked.

  ```bash
  # Verify allowed origin works
  curl -s -H "Origin: https://drolosoft.com" \
    -X OPTIONS \
    -D - \
    https://drolosoft.com/api/soundinbox/licenses/validate 2>&1 | grep -i "access-control"
  ```
  Expected: `Access-Control-Allow-Origin: https://drolosoft.com`

### Acceptance Criteria

- Health returns 200 with database connected
- Invalid license key returns 404
- Malformed key returns 400
- Method mismatch returns 405
- All four web pages return 200
- Admin without credentials returns 401
- Admin with credentials returns 200
- Rate limiting triggers 429 within 70 requests
- CORS blocks unauthorized origins

---

## Task 7: Lemon Squeezy Test Mode E2E

**What:** Run a complete purchase flow using Lemon Squeezy test mode to verify the webhook→license→email pipeline works end to end in production.

**Why:** This is the critical integration test. It validates that a real Lemon Squeezy webhook triggers license creation and email delivery on the production server. Skipping this risks a broken purchase flow on launch day.

### Steps

- [ ] **7.1** Enable test mode in Lemon Squeezy:
  - Go to https://app.lemonsqueezy.com
  - Navigate to: **Settings > General**
  - Toggle **Test Mode** ON (the dashboard header should show a "Test Mode" indicator)
  - Verify the webhook is also in test mode (webhooks created in test mode only fire for test purchases)

- [ ] **7.2** Create a test purchase:
  - Open the checkout URL with test mode: add `?test=true` to the checkout URL if needed, or use the test mode checkout link from the dashboard
  - Complete the purchase using Lemon Squeezy's test card:
    - Card number: `4242 4242 4242 4242`
    - Expiry: any future date (e.g., `12/29`)
    - CVC: any 3 digits (e.g., `123`)
    - Email: use `txeo.msx@gmail.com` for delivery verification
  - Click **Pay**

- [ ] **7.3** Verify webhook was received (within 30 seconds of purchase):
  ```bash
  curl -s -u "admin:<SOUNDINBOX_ADMIN_PASS>" \
    https://drolosoft.com/admin/soundinbox/webhooks | head -100
  ```
  Look for an entry with:
  - `event_name`: `order_created`
  - `signature_valid`: `1` (true)
  - `status`: `completed`

  Alternative — check server logs:
  ```bash
  ssh production "journalctl -u drolosoft -n 50 --no-pager | grep -i webhook"
  ```

- [ ] **7.4** Verify license was created:
  ```bash
  curl -s -u "admin:<SOUNDINBOX_ADMIN_PASS>" \
    https://drolosoft.com/admin/soundinbox/licenses
  ```
  Look for a license with:
  - `customer_email`: `txeo.msx@gmail.com`
  - `status`: `active`
  - `max_activations`: `3`
  - `license_key`: a key in the format `XXXXX-XXXXX-XXXXX-XXXXX-XXXXX`

- [ ] **7.5** Verify the license email was sent:
  - Check inbox at `txeo.msx@gmail.com` for subject "Your SoundInbox Pro License Key"
  - Also check the admin panel for `email_sent` flag:
    ```bash
    curl -s -u "admin:<SOUNDINBOX_ADMIN_PASS>" \
      "https://drolosoft.com/admin/soundinbox/licenses" | grep -o '"email_sent":[0-9]*'
    ```
    Expected: `"email_sent":1`
  - Also verify in SendGrid: **Activity Feed** should show the delivered email

- [ ] **7.6** Copy the license key from the admin panel or from the email. Save it for use in Tasks 8-12:
  ```
  TEST_LICENSE_KEY=<XXXXX-XXXXX-XXXXX-XXXXX-XXXXX from admin or email>
  ```

- [ ] **7.7** Validate the test license key via API:
  ```bash
  curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/validate \
    -H "Content-Type: application/json" \
    -d "{\"license_key\":\"$TEST_LICENSE_KEY\"}"
  ```
  Expected:
  ```json
  {
    "valid": true,
    "message": "License key is valid and active",
    "status": "active",
    "tier": "pro",
    "server_time": "2026-04-21T...",
    "features": {
      "max_accounts": 5
    }
  }
  ```

- [ ] **7.8** Test activation via curl (simulating a macOS client):
  ```bash
  curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/activate \
    -H "Content-Type: application/json" \
    -d "{
      \"license_key\":\"$TEST_LICENSE_KEY\",
      \"device_id\":\"E2E-TEST-DEVICE-001\",
      \"device_name\":\"E2E Test Mac\",
      \"device_model\":\"MacBookPro18,1\",
      \"os_version\":\"15.2\",
      \"app_version\":\"1.0.0\"
    }" \
    -w "\nHTTP Status: %{http_code}\n"
  ```
  Expected:
  ```json
  {
    "success": true,
    "message": "Device activated successfully",
    "activation_id": "1",
    "activated_at": "2026-04-21T...",
    "device_name": "E2E Test Mac",
    "tier": "pro",
    "features": {
      "max_accounts": 5
    }
  }
  HTTP Status: 201
  ```

- [ ] **7.9** Deactivate the test device (clean up for Task 8):
  ```bash
  curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/deactivate \
    -H "Content-Type: application/json" \
    -d "{
      \"license_key\":\"$TEST_LICENSE_KEY\",
      \"device_id\":\"E2E-TEST-DEVICE-001\"
    }" \
    -w "\nHTTP Status: %{http_code}\n"
  ```
  Expected:
  ```json
  {
    "success": true,
    "message": "Device deactivated successfully",
    "license": {
      "license_key": "XXXXX-XXXXX-XXXXX-XXXXX-XXXXX",
      "current_activations": 0,
      "max_activations": 3
    }
  }
  HTTP Status: 200
  ```

### Acceptance Criteria

- Webhook received and logged with valid signature
- License created with correct email, status, and max_activations
- Email delivered to inbox (not spam)
- License key validates as active with Pro tier and `max_accounts: 5`
- Activation returns 201 with correct features
- Deactivation returns 200 and decrements activation count

---

## Task 8: macOS Client E2E with Test License

**What:** Test the complete license activation flow using the real SoundInbox macOS app with the test license key from Task 7.

**Why:** This validates the Swift client integration — Keychain storage, API communication, UI state transitions, and feature gate enforcement — using a real license key from a real purchase.

### Steps

- [ ] **8.1** Build and launch SoundInbox:
  ```bash
  cd /Users/txeo/Git/mac/sound-inbox-mac
  xcodebuild -scheme SoundInbox -configuration Debug build 2>&1 | tail -5
  
  # Kill any running instance
  pkill -f "SoundInbox" 2>/dev/null || true
  
  # Launch the app
  open -a SoundInbox
  ```

- [ ] **8.2** Verify the app starts in Free tier:
  - Open the SoundInbox popover from the menu bar
  - Go to **Settings > License**
  - Verify it shows "Free" tier with 1 account limit
  - Verify the license key field is empty

- [ ] **8.3** Enter the test license key:
  - In Settings > License, enter the `TEST_LICENSE_KEY` from Task 7.6
  - The key should auto-format as you type (uppercase, dashes every 5 characters)
  - Verify format validation passes (no inline error)

- [ ] **8.4** Click **Activate**:
  - Expected: Success animation plays
  - License status changes to "Pro"
  - Max accounts shows 5
  - The activation response should be 201 (first activation on this device)

- [ ] **8.5** Verify Pro tier is active:
  - Settings > License should show:
    - Status: **Pro**
    - License key: masked as `XXXXX-****-****-****-XXXXX`
    - Device: current Mac's name
  - Try to add a 2nd email account — the upgrade prompt should NOT appear (Pro unlocked)

- [ ] **8.6** Test deactivation from the app:
  - In Settings > License, click **Deactivate**
  - Confirm the dialog
  - Expected: Status reverts to "Free", license key is cleared
  - Verify in Keychain: no `com.soundinbox.license` entry remains

- [ ] **8.7** Test re-activation (idempotent):
  - Enter the same license key again
  - Click **Activate**
  - Expected: Success (201 on fresh activation after deactivation)
  - If the device was already active (no deactivation happened), expect 200 with "Device already activated"

- [ ] **8.8** Verify persistence across app restart:
  - Quit SoundInbox completely
  - Relaunch the app
  - Go to Settings > License
  - Expected: Still shows "Pro" tier, license key is masked, device is active
  - This confirms Keychain + UserDefaults persistence is working

### Acceptance Criteria

- App starts in Free tier with no license
- License key entry works with auto-formatting
- Activation succeeds and transitions to Pro tier
- Adding a 2nd account is allowed in Pro tier
- Deactivation clears license and reverts to Free
- Re-activation works correctly
- Pro status persists across app restarts

---

## Task 9: Device Limit Testing

**What:** Verify that the 3-device activation limit is enforced correctly — a 4th device is rejected, and deactivating one device frees a slot.

**Why:** The license allows 3 simultaneous devices. Without testing this, a bug could allow unlimited activations (revenue loss) or block legitimate users (support burden).

### Steps

- [ ] **9.1** Activate device 1:
  ```bash
  curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/activate \
    -H "Content-Type: application/json" \
    -d "{
      \"license_key\":\"$TEST_LICENSE_KEY\",
      \"device_id\":\"DEVICE-LIMIT-001\",
      \"device_name\":\"MacBook Pro (Work)\",
      \"device_model\":\"MacBookPro18,1\",
      \"os_version\":\"15.2\",
      \"app_version\":\"1.0.0\"
    }" \
    -w "\nHTTP Status: %{http_code}\n"
  ```
  Expected: `201 Created`

- [ ] **9.2** Activate device 2:
  ```bash
  curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/activate \
    -H "Content-Type: application/json" \
    -d "{
      \"license_key\":\"$TEST_LICENSE_KEY\",
      \"device_id\":\"DEVICE-LIMIT-002\",
      \"device_name\":\"Mac Mini (Home)\",
      \"device_model\":\"Macmini9,1\",
      \"os_version\":\"15.2\",
      \"app_version\":\"1.0.0\"
    }" \
    -w "\nHTTP Status: %{http_code}\n"
  ```
  Expected: `201 Created`

- [ ] **9.3** Activate device 3:
  ```bash
  curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/activate \
    -H "Content-Type: application/json" \
    -d "{
      \"license_key\":\"$TEST_LICENSE_KEY\",
      \"device_id\":\"DEVICE-LIMIT-003\",
      \"device_name\":\"iMac (Studio)\",
      \"device_model\":\"iMac21,1\",
      \"os_version\":\"15.2\",
      \"app_version\":\"1.0.0\"
    }" \
    -w "\nHTTP Status: %{http_code}\n"
  ```
  Expected: `201 Created`

- [ ] **9.4** Attempt to activate device 4 (should be rejected):
  ```bash
  curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/activate \
    -H "Content-Type: application/json" \
    -d "{
      \"license_key\":\"$TEST_LICENSE_KEY\",
      \"device_id\":\"DEVICE-LIMIT-004\",
      \"device_name\":\"MacBook Air (Travel)\",
      \"device_model\":\"MacBookAir10,1\",
      \"os_version\":\"15.2\",
      \"app_version\":\"1.0.0\"
    }" \
    -w "\nHTTP Status: %{http_code}\n"
  ```
  Expected:
  ```json
  {
    "success": false,
    "error": "Activation limit reached",
    "message": "This license is already activated on 3 device(s). Please deactivate a device to activate a new one.",
    "current_activations": 3,
    "max_activations": 3,
    "active_devices": [
      {"device_id": "DEVICE-LIMIT-001", "device_name": "MacBook Pro (Work)", ...},
      {"device_id": "DEVICE-LIMIT-002", "device_name": "Mac Mini (Home)", ...},
      {"device_id": "DEVICE-LIMIT-003", "device_name": "iMac (Studio)", ...}
    ]
  }
  HTTP Status: 403
  ```

- [ ] **9.5** Deactivate device 1 to free a slot:
  ```bash
  curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/deactivate \
    -H "Content-Type: application/json" \
    -d "{
      \"license_key\":\"$TEST_LICENSE_KEY\",
      \"device_id\":\"DEVICE-LIMIT-001\"
    }" \
    -w "\nHTTP Status: %{http_code}\n"
  ```
  Expected: `200 OK` with `current_activations: 2`

- [ ] **9.6** Retry device 4 activation (should succeed now):
  ```bash
  curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/activate \
    -H "Content-Type: application/json" \
    -d "{
      \"license_key\":\"$TEST_LICENSE_KEY\",
      \"device_id\":\"DEVICE-LIMIT-004\",
      \"device_name\":\"MacBook Air (Travel)\",
      \"device_model\":\"MacBookAir10,1\",
      \"os_version\":\"15.2\",
      \"app_version\":\"1.0.0\"
    }" \
    -w "\nHTTP Status: %{http_code}\n"
  ```
  Expected: `201 Created` with `features.max_accounts: 5`

- [ ] **9.7** Test idempotent re-activation (same device, same key):
  ```bash
  curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/activate \
    -H "Content-Type: application/json" \
    -d "{
      \"license_key\":\"$TEST_LICENSE_KEY\",
      \"device_id\":\"DEVICE-LIMIT-004\",
      \"device_name\":\"MacBook Air (Travel)\",
      \"device_model\":\"MacBookAir10,1\",
      \"os_version\":\"15.2\",
      \"app_version\":\"1.0.0\"
    }" \
    -w "\nHTTP Status: %{http_code}\n"
  ```
  Expected: `200 OK` with "Device already activated" — does NOT consume an additional slot.

- [ ] **9.8** Clean up — deactivate all test devices:
  ```bash
  for DEVICE in DEVICE-LIMIT-002 DEVICE-LIMIT-003 DEVICE-LIMIT-004; do
    curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/deactivate \
      -H "Content-Type: application/json" \
      -d "{\"license_key\":\"$TEST_LICENSE_KEY\",\"device_id\":\"$DEVICE\"}"
    echo ""
  done
  ```

### Acceptance Criteria

- Devices 1-3 activate successfully (201 each)
- Device 4 is rejected with 403 and a list of 3 active devices
- After deactivating device 1, device 4 activates successfully (201)
- Re-activation of same device is idempotent (200, no extra slot consumed)

---

## Task 10: Refund Flow Testing

**What:** Trigger a refund in Lemon Squeezy test mode and verify the complete refund cascade: webhook received, license revoked, activations deactivated, macOS client detects revocation.

**Why:** Refunds must automatically revoke access. Without this, refunded customers keep Pro features indefinitely.

### Steps

- [ ] **10.1** First, ensure the test license has at least one active device for the refund to affect:
  ```bash
  curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/activate \
    -H "Content-Type: application/json" \
    -d "{
      \"license_key\":\"$TEST_LICENSE_KEY\",
      \"device_id\":\"REFUND-TEST-DEVICE\",
      \"device_name\":\"Refund Test Mac\",
      \"device_model\":\"MacBookPro18,1\",
      \"os_version\":\"15.2\",
      \"app_version\":\"1.0.0\"
    }" \
    -w "\nHTTP Status: %{http_code}\n"
  ```
  Expected: `201` or `200` (if already activated)

- [ ] **10.2** Trigger refund in Lemon Squeezy:
  - Go to https://app.lemonsqueezy.com (test mode should still be on)
  - Navigate to: **Orders**
  - Find the test order from Task 7
  - Click **Refund** > Confirm
  - This will fire an `order_refunded` webhook

- [ ] **10.3** Verify the refund webhook was received (within 30 seconds):
  ```bash
  curl -s -u "admin:<SOUNDINBOX_ADMIN_PASS>" \
    https://drolosoft.com/admin/soundinbox/webhooks | grep -A5 "order_refunded"
  ```
  Expected: An entry with `event_name: order_refunded`, `signature_valid: 1`, `status: completed`.

- [ ] **10.4** Verify the license status changed to "refunded":
  ```bash
  curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/validate \
    -H "Content-Type: application/json" \
    -d "{\"license_key\":\"$TEST_LICENSE_KEY\"}"
  ```
  Expected:
  ```json
  {
    "valid": false,
    "message": "License is refunded",
    "status": "refunded",
    "features": null
  }
  ```

- [ ] **10.5** Verify all activations were deactivated:
  ```bash
  curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/activate \
    -H "Content-Type: application/json" \
    -d "{
      \"license_key\":\"$TEST_LICENSE_KEY\",
      \"device_id\":\"REFUND-TEST-DEVICE\",
      \"device_name\":\"Refund Test Mac\",
      \"device_model\":\"MacBookPro18,1\",
      \"os_version\":\"15.2\",
      \"app_version\":\"1.0.0\"
    }" \
    -w "\nHTTP Status: %{http_code}\n"
  ```
  Expected: Should fail — the license is refunded, so activation is not allowed. Expect `403` or `404` depending on how the backend handles refunded licenses.

- [ ] **10.6** Verify macOS client detects revocation:
  - If the SoundInbox app is still running from Task 8, trigger a background verification:
    - Wait for the app's next 7-day verification cycle, OR
    - Manually trigger by going to Settings > License and tapping any refresh/verify action
  - Expected behavior:
    - The client calls `POST /api/soundinbox/licenses/validate`
    - Server returns `status: "refunded"`
    - Client immediately reverts to Free tier
    - Client shows message: "Your license has been refunded."
    - Client clears license key from Keychain
    - Extra accounts (if any) become paused, not deleted

- [ ] **10.7** Since the test license is now refunded, generate a new test license for remaining tasks:
  - Either create a new test purchase in Lemon Squeezy (repeat Task 7.2), OR
  - Generate a license manually via admin:
    ```bash
    curl -s -X POST -u "admin:<SOUNDINBOX_ADMIN_PASS>" \
      https://drolosoft.com/admin/soundinbox/licenses/generate \
      -H "Content-Type: application/json" \
      -d '{"customer_email":"txeo.msx@gmail.com","customer_name":"Test User"}'
    ```
  - Save the new key:
    ```
    TEST_LICENSE_KEY_2=<new key from admin response or email>
    ```

### Acceptance Criteria

- `order_refunded` webhook received with valid signature
- License status changed from "active" to "refunded"
- All device activations were deactivated
- Validate returns `valid: false, status: "refunded"`
- macOS client detects revocation and reverts to Free tier
- New test license is generated for remaining tasks

---

## Task 11: Duplicate Webhook Testing (Idempotency)

**What:** Send the same `order_created` webhook twice and verify only one license is created and only one email is sent.

**Why:** Lemon Squeezy may retry webhooks on timeout or network issues. Without idempotency, a retry creates a duplicate license and sends a duplicate email, confusing the customer.

### Steps

- [ ] **11.1** Check the current license count in admin:
  ```bash
  curl -s -u "admin:<SOUNDINBOX_ADMIN_PASS>" \
    https://drolosoft.com/admin/soundinbox/ | grep -o "Total Licenses: [0-9]*"
  ```
  Record this number as `BEFORE_COUNT`.

- [ ] **11.2** Create a new test purchase in Lemon Squeezy test mode (follow Task 7.2):
  - Complete the checkout
  - Wait for the webhook to be processed (30 seconds)

- [ ] **11.3** Verify one license was created:
  ```bash
  curl -s -u "admin:<SOUNDINBOX_ADMIN_PASS>" \
    https://drolosoft.com/admin/soundinbox/ | grep -o "Total Licenses: [0-9]*"
  ```
  Expected: `BEFORE_COUNT + 1`

- [ ] **11.4** Find the webhook payload for this order in the admin logs:
  ```bash
  curl -s -u "admin:<SOUNDINBOX_ADMIN_PASS>" \
    https://drolosoft.com/admin/soundinbox/webhooks
  ```
  Look for the most recent `order_created` entry. Note the `order_id`.

- [ ] **11.5** Manually replay the webhook (simulate Lemon Squeezy retry). This requires constructing a valid signed request. From the server logs or admin panel, get the raw webhook payload, then:
  ```bash
  # Get the webhook payload from the admin panel (or from server logs)
  # Replace WEBHOOK_PAYLOAD with the actual JSON body
  WEBHOOK_PAYLOAD='<exact JSON payload from the webhook log>'
  
  # Compute the HMAC-SHA256 signature
  SIGNATURE=$(echo -n "$WEBHOOK_PAYLOAD" | openssl dgst -sha256 -hmac "<SOUNDINBOX_WEBHOOK_SECRET>" | awk '{print $NF}')
  
  # Send the duplicate webhook
  curl -s -X POST https://drolosoft.com/api/soundinbox/webhooks/lemonsqueezy \
    -H "Content-Type: application/json" \
    -H "X-Signature: $SIGNATURE" \
    -d "$WEBHOOK_PAYLOAD" \
    -w "\nHTTP Status: %{http_code}\n"
  ```
  Expected: `200 OK` with `{"status":"accepted"}`

- [ ] **11.6** Wait 10 seconds for async processing, then verify license count is unchanged:
  ```bash
  sleep 10
  curl -s -u "admin:<SOUNDINBOX_ADMIN_PASS>" \
    https://drolosoft.com/admin/soundinbox/ | grep -o "Total Licenses: [0-9]*"
  ```
  Expected: Same as step 11.3 — still `BEFORE_COUNT + 1` (no duplicate)

- [ ] **11.7** Check webhook logs for the idempotent replay:
  ```bash
  curl -s -u "admin:<SOUNDINBOX_ADMIN_PASS>" \
    https://drolosoft.com/admin/soundinbox/webhooks
  ```
  Expected: Two entries for the same `order_id` — the second should be logged as an idempotent replay (check the `status` or any note field).

- [ ] **11.8** Verify only one email was sent. Check:
  - SendGrid Activity Feed: should show only one email to this customer for this purchase
  - Admin license detail: `email_sent` count should be `1`, not `2`
  ```bash
  # Check the license detail for email_sent count
  curl -s -u "admin:<SOUNDINBOX_ADMIN_PASS>" \
    "https://drolosoft.com/admin/soundinbox/licenses" | grep -o '"email_sent":[0-9]*'
  ```

### Acceptance Criteria

- Duplicate webhook returns 200 (accepted) without error
- Only one license exists for the order (no duplicate)
- Only one email was sent (email_sent = 1, not 2)
- Webhook log shows the second request as an idempotent replay

---

## Task 12: Offline Grace Period Testing

**What:** Verify the macOS client's offline grace period behavior: Pro continues for 30 days without warning, shows a notice at 30 days, and reverts to Free at 90 days. Reconnecting restores Pro immediately.

**Why:** Users must not be punished for temporary offline periods. But perpetual offline use must eventually require re-verification to prevent piracy.

### Steps

- [ ] **12.1** Ensure the app is activated with a valid license:
  - Launch SoundInbox
  - Verify Settings > License shows "Pro" status
  - Note the `lastVerified` date (visible in UserDefaults or Settings UI)

- [ ] **12.2** Simulate offline by blocking the API server:
  ```bash
  # Add an entry to /etc/hosts to block drolosoft.com
  sudo sh -c 'echo "127.0.0.1 drolosoft.com" >> /etc/hosts'
  
  # Verify the block works
  curl -s --connect-timeout 5 https://drolosoft.com/api/soundinbox/health
  # Expected: Connection refused or timeout
  ```

- [ ] **12.3** Test 7-day verification (should pass silently):
  - The app checks every 7 days. To simulate, you can:
    - Option A: Manually set `lastVerified` in UserDefaults to 8 days ago:
      ```bash
      defaults write com.drolosoft.SoundInbox lastVerificationDate -date "$(date -v-8d +%Y-%m-%dT%H:%M:%SZ)"
      ```
    - Option B: Wait for the natural timer (not practical for testing)
  - Relaunch the app:
    ```bash
    pkill -f "SoundInbox" 2>/dev/null; sleep 1; open -a SoundInbox
    ```
  - Expected: App still shows Pro. Verification fails silently (network error). No UI warning.

- [ ] **12.4** Test 30-day warning:
  - Set `lastVerified` to 31 days ago:
    ```bash
    defaults write com.drolosoft.SoundInbox lastVerificationDate -date "$(date -v-31d +%Y-%m-%dT%H:%M:%SZ)"
    ```
  - Relaunch the app:
    ```bash
    pkill -f "SoundInbox" 2>/dev/null; sleep 1; open -a SoundInbox
    ```
  - Expected: App still works in Pro mode, but shows a subtle warning: "Please connect to verify your license" (banner or notification)

- [ ] **12.5** Test 90-day expiry:
  - Set `lastVerified` to 91 days ago:
    ```bash
    defaults write com.drolosoft.SoundInbox lastVerificationDate -date "$(date -v-91d +%Y-%m-%dT%H:%M:%SZ)"
    ```
  - Relaunch the app:
    ```bash
    pkill -f "SoundInbox" 2>/dev/null; sleep 1; open -a SoundInbox
    ```
  - Expected:
    - Tier reverts to Free (1 account)
    - Message shown: "License verification required. Connect to restore Pro features."
    - Extra accounts (2-5) become paused — they are dimmed with "Paused" badge
    - Extra accounts are NOT deleted
    - First/oldest account remains active

- [ ] **12.6** Restore connectivity and verify Pro restoration:
  ```bash
  # Remove the /etc/hosts block
  sudo sed -i '' '/127.0.0.1 drolosoft.com/d' /etc/hosts
  
  # Verify connectivity restored
  curl -s https://drolosoft.com/api/soundinbox/health
  # Expected: {"status":"ok",...}
  ```

  - Relaunch the app (or wait for next verification attempt):
    ```bash
    pkill -f "SoundInbox" 2>/dev/null; sleep 1; open -a SoundInbox
    ```
  - Expected:
    - App contacts server, validates license successfully
    - Tier restores to Pro
    - All paused accounts resume automatically
    - No data was lost

- [ ] **12.7** Clean up UserDefaults:
  ```bash
  # Reset the lastVerificationDate to current time
  defaults delete com.drolosoft.SoundInbox lastVerificationDate
  ```

### Acceptance Criteria

- 7 days offline: Pro works, no warning, silent verification failure
- 30 days offline: Pro works, subtle warning appears
- 90 days offline: Reverts to Free, paused accounts (not deleted), clear message
- Reconnecting: Pro restored immediately, paused accounts resume
- `/etc/hosts` cleaned up after testing

---

## Task 13: SQLite Backup Setup

**What:** Configure an hourly cron job on the production server to back up the SQLite database, with 7-day retention.

**Why:** The SQLite database contains all licenses, orders, and activation records. A corrupted or lost database means lost customer data and no way to validate licenses.

### Steps

- [ ] **13.1** Create the backup script on the production server:
  ```bash
  ssh production "cat > /opt/drolosoft/backup-db.sh << 'SCRIPT'
#!/bin/bash
# SoundInbox SQLite Backup Script
# Runs hourly via cron, keeps 7 days of backups

DB_PATH=/opt/drolosoft/data/drolosoft.db
BACKUP_DIR=/opt/drolosoft/data/backups
TIMESTAMP=\$(date +%Y%m%d-%H%M%S)
BACKUP_FILE=\$BACKUP_DIR/drolosoft-\$TIMESTAMP.db
RETENTION_DAYS=7

# Create backup directory if missing
mkdir -p \$BACKUP_DIR

# Check database exists
if [ ! -f \$DB_PATH ]; then
  echo \"ERROR: Database not found at \$DB_PATH\" >&2
  exit 1
fi

# Use SQLite's .backup command for safe copy (handles WAL mode)
sqlite3 \$DB_PATH \".backup '\$BACKUP_FILE'\"

if [ \$? -eq 0 ]; then
  echo \"Backup created: \$BACKUP_FILE (\$(du -h \$BACKUP_FILE | cut -f1))\"
else
  # Fallback: file copy (safe if no active writes)
  cp \$DB_PATH \$BACKUP_FILE
  echo \"Backup created (file copy fallback): \$BACKUP_FILE\"
fi

# Delete backups older than retention period
find \$BACKUP_DIR -name \"drolosoft-*.db\" -mtime +\$RETENTION_DAYS -delete
echo \"Cleaned backups older than \$RETENTION_DAYS days\"
SCRIPT"

ssh production "chmod +x /opt/drolosoft/backup-db.sh"
  ```

- [ ] **13.2** Install the cron job:
  ```bash
  ssh production "crontab -l 2>/dev/null | grep -v backup-db.sh | { cat; echo '0 * * * * /opt/drolosoft/backup-db.sh >> /opt/drolosoft/data/backups/backup.log 2>&1'; } | crontab -"
  ```

  Verify:
  ```bash
  ssh production "crontab -l | grep backup"
  # Expected: 0 * * * * /opt/drolosoft/backup-db.sh >> /opt/drolosoft/data/backups/backup.log 2>&1
  ```

- [ ] **13.3** Run the backup script manually to test:
  ```bash
  ssh production "/opt/drolosoft/backup-db.sh"
  # Expected: "Backup created: /opt/drolosoft/data/backups/drolosoft-20260421-XXXXXX.db (XXK)"
  ```

- [ ] **13.4** Verify the backup file exists and is valid:
  ```bash
  ssh production "ls -la /opt/drolosoft/data/backups/"
  # Expected: at least one .db file
  
  ssh production "sqlite3 /opt/drolosoft/data/backups/drolosoft-*.db 'SELECT count(*) FROM si_licenses;'"
  # Expected: a number (the license count)
  ```

- [ ] **13.5** Test restore from backup (on a test path, not overwriting production):
  ```bash
  ssh production "LATEST=\$(ls -t /opt/drolosoft/data/backups/drolosoft-*.db | head -1) && \
    sqlite3 \$LATEST 'SELECT license_key, customer_email, status FROM si_licenses LIMIT 5;'"
  ```
  Expected: License records from the backup, matching what you see in the admin panel.

  Full restore procedure (for documentation, do NOT run in production unless needed):
  ```bash
  # EMERGENCY RESTORE PROCEDURE (use only if production DB is corrupted)
  # 1. Stop the service
  ssh production "sudo systemctl stop drolosoft"
  
  # 2. Back up the corrupted database
  ssh production "mv /opt/drolosoft/data/drolosoft.db /opt/drolosoft/data/drolosoft-corrupted-$(date +%Y%m%d).db"
  
  # 3. Restore from latest backup
  ssh production "LATEST=\$(ls -t /opt/drolosoft/data/backups/drolosoft-*.db | head -1) && cp \$LATEST /opt/drolosoft/data/drolosoft.db"
  
  # 4. Restart the service
  ssh production "sudo systemctl start drolosoft"
  ```

### Acceptance Criteria

- Backup script exists at `/opt/drolosoft/backup-db.sh` and is executable
- Cron job runs hourly (every hour at minute 0)
- Manual backup creates a valid SQLite file
- Backup file can be queried and contains real data
- Backups older than 7 days are automatically cleaned

---

## Task 14: Security Verification

**What:** Verify all security controls are functioning correctly: robots.txt, admin auth, webhook signature validation, rate limiting, and CORS.

**Why:** Security flaws in a payment system can lead to unauthorized access, webhook spoofing, or data exposure. Each control must be verified independently.

### Steps

- [ ] **14.1** Verify robots.txt disallows admin:
  ```bash
  curl -s https://drolosoft.com/robots.txt
  ```
  Expected output must include:
  ```
  Disallow: /admin/
  ```

- [ ] **14.2** Verify admin requires authentication:
  ```bash
  # No credentials
  curl -s -o /dev/null -w "%{http_code}" https://drolosoft.com/admin/soundinbox/
  # Expected: 401
  
  # Wrong credentials
  curl -s -o /dev/null -w "%{http_code}" -u "wrong:wrong" https://drolosoft.com/admin/soundinbox/
  # Expected: 401
  
  # Correct credentials
  curl -s -o /dev/null -w "%{http_code}" -u "admin:<SOUNDINBOX_ADMIN_PASS>" https://drolosoft.com/admin/soundinbox/
  # Expected: 200
  ```

- [ ] **14.3** Verify webhook rejects invalid signatures:
  ```bash
  # Missing signature header
  curl -s -X POST https://drolosoft.com/api/soundinbox/webhooks/lemonsqueezy \
    -H "Content-Type: application/json" \
    -d '{"meta":{"event_name":"order_created"}}' \
    -w "\nHTTP Status: %{http_code}\n"
  # Expected: 401 (no body — generic rejection)
  
  # Wrong signature
  curl -s -X POST https://drolosoft.com/api/soundinbox/webhooks/lemonsqueezy \
    -H "Content-Type: application/json" \
    -H "X-Signature: deadbeef0000000000000000000000000000000000000000000000000000000" \
    -d '{"meta":{"event_name":"order_created"}}' \
    -w "\nHTTP Status: %{http_code}\n"
  # Expected: 401 (no body — generic rejection, no "invalid signature" message)
  ```

- [ ] **14.4** Verify rate limiting protects license endpoints:
  ```bash
  # Rapid-fire 70 requests
  RATE_LIMITED=0
  for i in $(seq 1 70); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
      https://drolosoft.com/api/soundinbox/licenses/validate \
      -H "Content-Type: application/json" \
      -d '{"license_key":"AAAAA-BBBBB-CCCCC-DDDDD-EEEEE"}')
    if [ "$STATUS" = "429" ]; then
      RATE_LIMITED=1
      echo "PASS: Rate limited at request $i"
      break
    fi
  done
  
  if [ "$RATE_LIMITED" = "0" ]; then
    echo "FAIL: No rate limiting detected after 70 requests"
  fi
  ```
  Expected: `PASS` with rate limiting triggered before request 70.

- [ ] **14.5** Verify CORS blocks unauthorized origins:
  ```bash
  # Unauthorized origin
  curl -s -I -H "Origin: https://attacker.com" \
    -X POST https://drolosoft.com/api/soundinbox/licenses/validate \
    -H "Content-Type: application/json" \
    -d '{"license_key":"AAAAA-BBBBB-CCCCC-DDDDD-EEEEE"}' 2>&1 | grep -i "access-control-allow-origin"
  # Expected: No "Access-Control-Allow-Origin: https://attacker.com" header
  
  # Authorized origin
  curl -s -I -H "Origin: https://drolosoft.com" \
    -X POST https://drolosoft.com/api/soundinbox/licenses/validate \
    -H "Content-Type: application/json" \
    -d '{"license_key":"AAAAA-BBBBB-CCCCC-DDDDD-EEEEE"}' 2>&1 | grep -i "access-control-allow-origin"
  # Expected: Access-Control-Allow-Origin: https://drolosoft.com
  ```

- [ ] **14.6** Verify security headers are present:
  ```bash
  curl -s -I https://drolosoft.com/api/soundinbox/health 2>&1 | grep -iE "(x-content-type|x-frame-options|strict-transport)"
  ```
  Expected:
  ```
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Strict-Transport-Security: max-age=...
  ```

- [ ] **14.7** Verify input validation (stored XSS prevention):
  ```bash
  # Try to activate with an XSS payload in device_name
  curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/activate \
    -H "Content-Type: application/json" \
    -d "{
      \"license_key\":\"$TEST_LICENSE_KEY_2\",
      \"device_id\":\"XSS-TEST-001\",
      \"device_name\":\"<script>alert('xss')</script>\",
      \"device_model\":\"MacBookPro18,1\",
      \"os_version\":\"15.2\",
      \"app_version\":\"1.0.0\"
    }" \
    -w "\nHTTP Status: %{http_code}\n"
  ```
  Expected: Either `400` (rejected) or `201` with the device_name HTML-escaped in the response and database (no raw `<script>` stored).

- [ ] **14.8** Clean up XSS test device:
  ```bash
  curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/deactivate \
    -H "Content-Type: application/json" \
    -d "{\"license_key\":\"$TEST_LICENSE_KEY_2\",\"device_id\":\"XSS-TEST-001\"}"
  ```

### Acceptance Criteria

- robots.txt contains `Disallow: /admin/`
- Admin returns 401 without credentials, 200 with correct credentials
- Webhook returns 401 for missing or invalid signatures (no error details in body)
- Rate limiting triggers 429 within expected thresholds
- CORS blocks unauthorized origins, allows drolosoft.com
- Security headers (X-Content-Type-Options, X-Frame-Options) are present
- XSS payloads in device_name are sanitized or rejected

---

## Task 15: Go-Live Checklist

**What:** Switch from Lemon Squeezy test mode to live mode, update all URLs to production, and verify the complete flow one final time.

**Why:** Test mode and live mode use different API keys, webhook secrets, and checkout URLs. Missing any switch means payments fail or webhooks are silently dropped.

### Steps

- [ ] **15.1** Pre-flight verification — confirm all previous tasks passed:
  ```
  [ ] Task 1: Lemon Squeezy product configured
  [ ] Task 2: SendGrid email verified and DNS authenticated
  [ ] Task 3: Google OAuth consent screen updated
  [ ] Task 4: .env.production complete with real values
  [ ] Task 5: Backend deployed and healthy
  [ ] Task 6: All smoke tests passed
  [ ] Task 7: Lemon Squeezy test mode E2E passed
  [ ] Task 8: macOS client E2E passed
  [ ] Task 9: Device limit enforcement verified
  [ ] Task 10: Refund flow verified
  [ ] Task 11: Webhook idempotency verified
  [ ] Task 12: Offline grace period verified
  [ ] Task 13: SQLite backups configured
  [ ] Task 14: Security controls verified
  ```
  Every checkbox must be checked before proceeding.

- [ ] **15.2** Switch Lemon Squeezy from test to live mode:
  - Go to https://app.lemonsqueezy.com
  - Navigate to: **Settings > General**
  - Toggle **Test Mode** OFF
  - Verify the dashboard header no longer shows "Test Mode"

- [ ] **15.3** Verify the live webhook is configured:
  - Navigate to: **Settings > Webhooks**
  - Confirm the webhook URL is: `https://drolosoft.com/api/soundinbox/webhooks/lemonsqueezy`
  - Confirm events: `order_created`, `order_refunded`
  - **Important:** If test mode and live mode have separate webhook configurations, ensure the live webhook is set up correctly. The signing secret may differ between modes — update `SOUNDINBOX_WEBHOOK_SECRET` on the server if needed.

- [ ] **15.4** Get the live checkout URL:
  - Go to the SoundInbox Pro product in Lemon Squeezy
  - Click **Share** to get the live checkout link
  - It should look like: `https://drolosoft.lemonsqueezy.com/buy/<variant-uuid>`
  - If the live UUID differs from the test UUID, update:
    ```bash
    ssh production "sudo sed -i 's|SOUNDINBOX_LEMONSQUEEZY_CHECKOUT=.*|SOUNDINBOX_LEMONSQUEEZY_CHECKOUT=<new live URL>|' /etc/drolosoft/env && sudo systemctl restart drolosoft"
    ```

- [ ] **15.5** Update the pricing page "Buy Now" button:
  - The button URL is driven by `SOUNDINBOX_LEMONSQUEEZY_CHECKOUT` env var
  - Verify it points to the live checkout:
    ```bash
    curl -s https://drolosoft.com/soundinbox/pricing | grep -o 'https://drolosoft.lemonsqueezy.com/buy/[^"]*'
    ```
  - Open the URL in a browser and verify it shows the real checkout page (not test mode)

- [ ] **15.6** Verify the macOS app points to production API:
  - In the SoundInbox source code, confirm the API base URL is:
    ```
    https://drolosoft.com/api/soundinbox
    ```
  - This should already be the case, but verify:
    ```bash
    grep -r "drolosoft.com/api/soundinbox" /Users/txeo/Git/mac/sound-inbox-mac/SoundInbox/
    ```

- [ ] **15.7** Run one final complete verification:
  ```bash
  # 1. Health check
  curl -s https://drolosoft.com/api/soundinbox/health
  
  # 2. Pricing page loads with live checkout URL
  curl -s -o /dev/null -w "%{http_code}" https://drolosoft.com/soundinbox/pricing
  
  # 3. Privacy page loads (Google OAuth requirement)
  curl -s -o /dev/null -w "%{http_code}" https://drolosoft.com/soundinbox/privacy
  
  # 4. Admin dashboard accessible
  curl -s -o /dev/null -w "%{http_code}" -u "admin:<SOUNDINBOX_ADMIN_PASS>" https://drolosoft.com/admin/soundinbox/
  
  # 5. Validate API responds
  curl -s -X POST https://drolosoft.com/api/soundinbox/licenses/validate \
    -H "Content-Type: application/json" \
    -d '{"license_key":"AAAAA-BBBBB-CCCCC-DDDDD-EEEEE"}' \
    -o /dev/null -w "%{http_code}"
  ```
  Expected: `200`, `200`, `200`, `200`, `404`

- [ ] **15.8** Monitor for the first real purchase:
  - Keep the admin dashboard open: `https://drolosoft.com/admin/soundinbox/`
  - Watch for the first `order_created` webhook in the webhook logs
  - Verify the license is created and email is delivered
  - If you want to test with your own purchase:
    1. Open the live checkout URL
    2. Complete a real purchase with a real card
    3. Verify the entire flow (webhook → license → email → activation)
    4. Refund yourself afterward if desired

### Acceptance Criteria

- Lemon Squeezy is in live mode (not test)
- Checkout URL on pricing page leads to real payment page
- Webhook is configured for live mode with correct signing secret
- macOS app uses production API URL
- All endpoints respond correctly in final verification
- System is ready for first real purchase

---

## Task 16: Post-Launch Monitoring

**What:** Establish a monitoring routine for the first week after launch to catch issues before they affect customers.

**Why:** First-week issues (webhook failures, email delivery problems, edge-case bugs) are normal. Catching them quickly means fewer support tickets and better customer experience.

### Steps

- [ ] **16.1** Set up daily monitoring checks (run these each day for the first week):
  ```bash
  # Health check
  curl -s https://drolosoft.com/api/soundinbox/health
  
  # Check service is running
  ssh production "sudo systemctl is-active drolosoft"
  
  # Check for errors in recent logs
  ssh production "journalctl -u drolosoft --since '24 hours ago' -p err --no-pager"
  
  # Check disk space (SQLite can grow)
  ssh production "df -h /opt/drolosoft/data/"
  ssh production "du -sh /opt/drolosoft/data/drolosoft.db"
  ```

- [ ] **16.2** Check admin dashboard daily:
  ```bash
  curl -s -u "admin:<SOUNDINBOX_ADMIN_PASS>" \
    https://drolosoft.com/admin/soundinbox/ 2>&1 | head -50
  ```
  Review:
  - Total licenses count (growing?)
  - Active licenses count
  - Failed webhooks (should be 0)
  - Unsent emails (should be 0)

- [ ] **16.3** Monitor webhook delivery in the admin panel:
  ```bash
  # Check for any failed webhooks
  curl -s -u "admin:<SOUNDINBOX_ADMIN_PASS>" \
    https://drolosoft.com/admin/soundinbox/webhooks | grep -c '"status":"failed"'
  # Expected: 0
  
  # Check for invalid signatures (possible attack attempts)
  curl -s -u "admin:<SOUNDINBOX_ADMIN_PASS>" \
    https://drolosoft.com/admin/soundinbox/webhooks | grep -c '"signature_valid":0'
  # Expected: 0 (or very few — investigate if > 0)
  ```

- [ ] **16.4** Monitor email delivery via SendGrid:
  - Log in to https://app.sendgrid.com
  - Navigate to: **Activity Feed**
  - Filter by: From = `hello@drolosoft.com`, Subject contains "SoundInbox"
  - Check for:
    - Bounces (invalid customer email)
    - Blocks (spam filter)
    - Deferred (temporary delivery issues)
  - All emails should show "Delivered" status

- [ ] **16.5** Watch for rate limit violations:
  ```bash
  ssh production "journalctl -u drolosoft --since '24 hours ago' --no-pager | grep -c '429'"
  # If > 100 in 24 hours, investigate: could be abuse or a misconfigured client
  ```

- [ ] **16.6** Verify SQLite backups are running:
  ```bash
  ssh production "ls -lt /opt/drolosoft/data/backups/ | head -5"
  # Expected: Recent backup files, one per hour
  
  ssh production "cat /opt/drolosoft/data/backups/backup.log | tail -10"
  # Expected: Recent log entries showing successful backups
  ```

- [ ] **16.7** Check for resource issues:
  ```bash
  # Memory usage
  ssh production "ps -o pid,rss,vsz,comm -p \$(pgrep -f drolosoft/server) 2>/dev/null"
  
  # Open file descriptors
  ssh production "ls /proc/\$(pgrep -f drolosoft/server)/fd 2>/dev/null | wc -l"
  
  # Database size growth
  ssh production "du -sh /opt/drolosoft/data/drolosoft.db"
  ```

- [ ] **16.8** After 7 days with no issues, reduce monitoring to weekly:
  - Continue running the health check daily (can be automated with a simple cron)
  - Review admin dashboard weekly
  - Review SendGrid delivery stats weekly
  - Review backup logs weekly

### Acceptance Criteria

- Health endpoint returns 200 consistently
- Zero failed webhooks in the first week
- All emails delivered (no bounces or blocks)
- Backups running on schedule with valid files
- No memory leaks or resource exhaustion
- System stable enough to reduce to weekly monitoring after 7 days
