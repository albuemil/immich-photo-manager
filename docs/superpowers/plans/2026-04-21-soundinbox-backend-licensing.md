# SoundInbox Backend Licensing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add license monetization system to the Drolosoft Go web server for SoundInbox Pro ($14.99 one-time).

**Architecture:** Extends existing Drolosoft server with SQLite database, product-agnostic licensing engine (reusable for Commando), Lemon Squeezy webhook integration, license API, admin dashboard, and web pages (pricing, download, privacy, changelog). Ports proven patterns from Commando reference implementation.

**Tech Stack:** Go 1.25+, modernc.org/sqlite, existing Drolosoft middleware chain, SendGrid SMTP, Lemon Squeezy webhooks, server-rendered HTML templates.

**Codebase:** `/Users/txeo/Git/mac/go/drolosoft/`
**Spec:** `/Users/txeo/Git/drolosoft/immich-photo-manager/docs/superpowers/specs/2026-04-20-soundinbox-monetization-design.md`
**Reference:** `/Users/txeo/Git/mac/go/commando-web/`

---

## Critical Context for Implementers

**Drolosoft server patterns (MUST follow):**
- Module path: `github.com/juanatsap/drolosoft`
- Route registration: `mux.HandleFunc(path, handler)` on `http.NewServeMux()`
- Middleware: `middleware.Default()(mux)` returns `middleware.Chain(Recovery, Logger, SecurityHeaders)(mux)`
- Config: `config.Load()` reads `.env` via `godotenv`, returns `*config.Config`
- Site pages: `SiteHandler.renderPage(w, r, "templateName", pageOpts{...})` parses partials glob + page template
- Handlers: constructor injection (`NewSiteHandler(store, dir, hotReload)`)
- Port: 2005
- Templates: `web/templates/site/pages/*.html` with partials at `web/templates/site/partials/*.html`
- No database currently — we are adding SQLite from scratch

**Commando patterns to port (adapt to Drolosoft):**
- Uses `modernc.org/sqlite` (pure Go, NO CGO) — we use this, NOT `mattn/go-sqlite3`
- Keygen: `GenerateLicenseKey()`, `ValidateLicenseKeyFormat()`, `NormalizeLicenseKey()` — port verbatim
- Webhook: `VerifySignature()`, `ParseLemonSqueezyWebhook()`, `ValidateWebhookPayload()` — port verbatim
- Email: `EmailService` with `SMTPConfig`, `LicenseEmailData`, multipart MIME — port and rebrand
- Rate limiter: Sliding window with cleanup goroutine — port the Commando version (simpler, better)
- Admin: HTTP Basic Auth with `crypto/subtle.ConstantTimeCompare` — port pattern
- Database: embedded SQL migrations, `database/sql` interface

**Key difference from Commando:** The licensing package (`internal/licensing/`) is product-agnostic. It takes a table prefix parameter so it can be reused for Commando later. SoundInbox uses prefix `si_`, Commando would use `cmd_`.

---

## Task 1: Add SQLite dependency and database package

**Files:**
- Modify: `/Users/txeo/Git/mac/go/drolosoft/go.mod`
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/database/database.go`
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/database/migrations/001_create_soundinbox_tables.sql`
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/database/database_test.go`

### Steps

- [ ] **1.1** Add `modernc.org/sqlite` to go.mod:

```bash
cd /Users/txeo/Git/mac/go/drolosoft && go get modernc.org/sqlite
```

This adds the pure-Go SQLite driver. No CGO required.

- [ ] **1.2** Create the database package at `/Users/txeo/Git/mac/go/drolosoft/internal/database/database.go`:

```go
// Package database provides SQLite database connectivity, migration management,
// and health checking for the Drolosoft application.
package database

import (
	"context"
	"database/sql"
	"embed"
	"fmt"
	"io/fs"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	_ "modernc.org/sqlite" // Pure-Go SQLite driver (no CGO)
)

//go:embed migrations/*.sql
var migrations embed.FS

// DB wraps the standard sql.DB with metadata.
type DB struct {
	*sql.DB
	Path     string
	IsMemory bool
}

// Open opens (or creates) a SQLite database at the given path.
// Pass ":memory:" for an in-memory database (useful in tests).
func Open(path string) (*DB, error) {
	isMemory := path == ":memory:"

	// Ensure parent directory exists for file-based databases.
	if !isMemory {
		dir := filepath.Dir(path)
		if err := os.MkdirAll(dir, 0755); err != nil {
			return nil, fmt.Errorf("database: create directory %s: %w", dir, err)
		}
	}

	// modernc.org/sqlite registers itself as driver "sqlite".
	dsn := path
	if !isMemory {
		// WAL mode for better concurrency; foreign keys on.
		dsn = path + "?_pragma=journal_mode(wal)&_pragma=foreign_keys(on)&_pragma=busy_timeout(5000)"
	} else {
		dsn = ":memory:?_pragma=foreign_keys(on)"
	}

	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, fmt.Errorf("database: open %s: %w", path, err)
	}

	// SQLite works best with a single writer connection.
	db.SetMaxOpenConns(1)
	db.SetMaxIdleConns(1)
	db.SetConnMaxLifetime(0)

	// Verify connectivity.
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	if err := db.PingContext(ctx); err != nil {
		db.Close()
		return nil, fmt.Errorf("database: ping %s: %w", path, err)
	}

	log.Printf("[db] Connected to SQLite database: %s", path)

	return &DB{
		DB:       db,
		Path:     path,
		IsMemory: isMemory,
	}, nil
}

// Migrate runs all embedded SQL migration files in alphabetical order.
// Migrations are idempotent (use IF NOT EXISTS).
func (db *DB) Migrate() error {
	log.Println("[db] Running database migrations...")

	entries, err := fs.ReadDir(migrations, "migrations")
	if err != nil {
		return fmt.Errorf("database: read migration dir: %w", err)
	}

	// Sort by filename to ensure correct order.
	sort.Slice(entries, func(i, j int) bool {
		return entries[i].Name() < entries[j].Name()
	})

	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".sql") {
			continue
		}

		content, err := migrations.ReadFile("migrations/" + entry.Name())
		if err != nil {
			return fmt.Errorf("database: read migration %s: %w", entry.Name(), err)
		}

		if _, err := db.Exec(string(content)); err != nil {
			return fmt.Errorf("database: execute migration %s: %w", entry.Name(), err)
		}

		log.Printf("[db] Applied migration: %s", entry.Name())
	}

	log.Println("[db] Migrations completed successfully")
	return nil
}

// HealthCheck verifies database connectivity with a 2-second timeout.
func (db *DB) HealthCheck() error {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		return fmt.Errorf("database: health check failed: %w", err)
	}

	return nil
}

// Close closes the database connection.
func (db *DB) Close() error {
	log.Println("[db] Closing database connection")
	return db.DB.Close()
}

// OpenTestDB creates an in-memory SQLite database with all migrations applied.
// Use in tests only.
func OpenTestDB() (*DB, error) {
	db, err := Open(":memory:")
	if err != nil {
		return nil, err
	}

	if err := db.Migrate(); err != nil {
		db.Close()
		return nil, err
	}

	return db, nil
}
```

- [ ] **1.3** Create the migration SQL at `/Users/txeo/Git/mac/go/drolosoft/internal/database/migrations/001_create_soundinbox_tables.sql`:

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

-- Updated_at triggers
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

- [ ] **1.4** Create database tests at `/Users/txeo/Git/mac/go/drolosoft/internal/database/database_test.go`:

```go
package database

import (
	"testing"
)

func TestOpenMemoryDatabase(t *testing.T) {
	db, err := Open(":memory:")
	if err != nil {
		t.Fatalf("Failed to open in-memory database: %v", err)
	}
	defer db.Close()

	if !db.IsMemory {
		t.Error("Expected IsMemory to be true")
	}

	if db.Path != ":memory:" {
		t.Errorf("Expected path ':memory:', got %q", db.Path)
	}
}

func TestMigrations(t *testing.T) {
	db, err := Open(":memory:")
	if err != nil {
		t.Fatalf("Failed to open database: %v", err)
	}
	defer db.Close()

	if err := db.Migrate(); err != nil {
		t.Fatalf("Migration failed: %v", err)
	}

	// Verify si_licenses table exists
	var tableName string
	err = db.QueryRow("SELECT name FROM sqlite_master WHERE type='table' AND name='si_licenses'").Scan(&tableName)
	if err != nil {
		t.Fatalf("si_licenses table not found: %v", err)
	}
	if tableName != "si_licenses" {
		t.Errorf("Expected table 'si_licenses', got %q", tableName)
	}

	// Verify si_activations table exists
	err = db.QueryRow("SELECT name FROM sqlite_master WHERE type='table' AND name='si_activations'").Scan(&tableName)
	if err != nil {
		t.Fatalf("si_activations table not found: %v", err)
	}

	// Verify si_orders table exists
	err = db.QueryRow("SELECT name FROM sqlite_master WHERE type='table' AND name='si_orders'").Scan(&tableName)
	if err != nil {
		t.Fatalf("si_orders table not found: %v", err)
	}

	// Verify si_webhook_logs table exists
	err = db.QueryRow("SELECT name FROM sqlite_master WHERE type='table' AND name='si_webhook_logs'").Scan(&tableName)
	if err != nil {
		t.Fatalf("si_webhook_logs table not found: %v", err)
	}
}

func TestMigrationsIdempotent(t *testing.T) {
	db, err := Open(":memory:")
	if err != nil {
		t.Fatalf("Failed to open database: %v", err)
	}
	defer db.Close()

	// Run migrations twice — should not error
	if err := db.Migrate(); err != nil {
		t.Fatalf("First migration failed: %v", err)
	}
	if err := db.Migrate(); err != nil {
		t.Fatalf("Second migration failed (not idempotent): %v", err)
	}
}

func TestHealthCheck(t *testing.T) {
	db, err := Open(":memory:")
	if err != nil {
		t.Fatalf("Failed to open database: %v", err)
	}
	defer db.Close()

	if err := db.HealthCheck(); err != nil {
		t.Fatalf("Health check failed: %v", err)
	}
}

func TestOpenTestDB(t *testing.T) {
	db, err := OpenTestDB()
	if err != nil {
		t.Fatalf("OpenTestDB failed: %v", err)
	}
	defer db.Close()

	// Insert a test row to verify schema
	_, err = db.Exec(`INSERT INTO si_licenses (license_key, order_id, customer_email, max_activations) VALUES (?, ?, ?, ?)`,
		"ABCDE-FGHIJ-KLMNO-PQRST-UVWXY", "ORDER-001", "test@example.com", 3)
	if err != nil {
		t.Fatalf("Failed to insert test license: %v", err)
	}

	var key string
	err = db.QueryRow("SELECT license_key FROM si_licenses WHERE order_id = ?", "ORDER-001").Scan(&key)
	if err != nil {
		t.Fatalf("Failed to query test license: %v", err)
	}
	if key != "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY" {
		t.Errorf("Expected key 'ABCDE-FGHIJ-KLMNO-PQRST-UVWXY', got %q", key)
	}
}
```

### Test

```bash
cd /Users/txeo/Git/mac/go/drolosoft && go test ./internal/database/ -v
```

Expected output: All 5 tests pass (`TestOpenMemoryDatabase`, `TestMigrations`, `TestMigrationsIdempotent`, `TestHealthCheck`, `TestOpenTestDB`).

### Commit

```
feat(db): add SQLite database package with embedded migrations

Add modernc.org/sqlite pure-Go driver (no CGO required).
Create database package with Open, Migrate, HealthCheck, and test helpers.
Include SoundInbox schema: si_licenses, si_activations, si_orders, si_webhook_logs.
```

---

## Task 2: Extend configuration

**Files:**
- Modify: `/Users/txeo/Git/mac/go/drolosoft/internal/config/config.go`
- Create: `/Users/txeo/Git/mac/go/drolosoft/.env.example` (or append to existing)
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/config/config_test.go`

### Steps

- [ ] **2.1** Modify `/Users/txeo/Git/mac/go/drolosoft/internal/config/config.go` to add SoundInbox fields. Add a new struct `SoundInboxConfig` and embed it in `Config`:

```go
// Package config provides configuration management for the Drolosoft application.
// It loads settings from environment variables with sensible defaults.
package config

import (
	"os"
	"strconv"
	"strings"

	"github.com/joho/godotenv"
)

// Config holds all application configuration
type Config struct {
	Server     ServerConfig
	Template   TemplateConfig
	SoundInbox SoundInboxConfig
}

// ServerConfig holds server-related settings
type ServerConfig struct {
	Port         string
	Host         string
	ReadTimeout  int // seconds
	WriteTimeout int // seconds
	IdleTimeout  int // seconds
}

// TemplateConfig holds template-related settings
type TemplateConfig struct {
	Dir       string
	HotReload bool
}

// SoundInboxConfig holds all SoundInbox licensing and payment settings
type SoundInboxConfig struct {
	// Database
	DBPath string

	// Lemon Squeezy
	WebhookSecret        string
	ProductID            string
	VariantID            string
	LemonSqueezyCheckout string

	// Licensing
	MaxActivations int

	// SMTP (SendGrid)
	SMTPHost      string
	SMTPPort      int
	SMTPUser      string
	SMTPPass      string
	SMTPFromName  string
	SMTPFromEmail string

	// URLs and contact
	SupportEmail  string
	DownloadURL   string
	ActivationURL string

	// Admin panel
	AdminUser string
	AdminPass string
}

// Environment returns the current environment (development/production)
func (c *Config) Environment() string {
	return os.Getenv("GO_ENV")
}

// IsDevelopment returns true if running in development mode
func (c *Config) IsDevelopment() bool {
	env := c.Environment()
	return env == "" || env == "development"
}

// IsProduction returns true if running in production mode
func (c *Config) IsProduction() bool {
	return c.Environment() == "production"
}

// Address returns the full server address (host:port)
func (c *Config) Address() string {
	if c.Server.Host != "" {
		return c.Server.Host + ":" + c.Server.Port
	}
	return "localhost:" + c.Server.Port
}

// Load reads configuration from environment variables with defaults
func Load() *Config {
	// Load .env file (ignore error if not found)
	_ = godotenv.Load()

	cfg := &Config{
		Server: ServerConfig{
			Port:         getEnv("PORT", "2005"),
			Host:         getEnv("HOST", ""),
			ReadTimeout:  getEnvInt("READ_TIMEOUT", 15),
			WriteTimeout: getEnvInt("WRITE_TIMEOUT", 15),
			IdleTimeout:  getEnvInt("IDLE_TIMEOUT", 60),
		},
		Template: TemplateConfig{
			Dir:       getEnv("TEMPLATE_DIR", "web/templates"),
			HotReload: getEnvBool("TEMPLATE_HOT_RELOAD", isDevelopment()),
		},
		SoundInbox: SoundInboxConfig{
			DBPath:               getEnv("SOUNDINBOX_DB_PATH", "data/drolosoft.db"),
			WebhookSecret:        getEnv("SOUNDINBOX_WEBHOOK_SECRET", ""),
			ProductID:            getEnv("SOUNDINBOX_PRODUCT_ID", ""),
			VariantID:            getEnv("SOUNDINBOX_VARIANT_ID", ""),
			LemonSqueezyCheckout: getEnv("SOUNDINBOX_LEMONSQUEEZY_CHECKOUT", ""),
			MaxActivations:       getEnvInt("SOUNDINBOX_MAX_ACTIVATIONS", 3),
			SMTPHost:             getEnv("SOUNDINBOX_SMTP_HOST", "smtp.sendgrid.net"),
			SMTPPort:             getEnvInt("SOUNDINBOX_SMTP_PORT", 587),
			SMTPUser:             getEnv("SOUNDINBOX_SMTP_USER", "apikey"),
			SMTPPass:             getEnv("SOUNDINBOX_SMTP_PASS", ""),
			SMTPFromName:         getEnv("SOUNDINBOX_SMTP_FROM_NAME", "SoundInbox"),
			SMTPFromEmail:        getEnv("SOUNDINBOX_SMTP_FROM_EMAIL", "hello@drolosoft.com"),
			SupportEmail:         getEnv("SOUNDINBOX_SUPPORT_EMAIL", "support@drolosoft.com"),
			DownloadURL:          getEnv("SOUNDINBOX_DOWNLOAD_URL", "https://drolosoft.com/soundinbox/download"),
			ActivationURL:        getEnv("SOUNDINBOX_ACTIVATION_URL", "https://drolosoft.com/soundinbox/download#activation"),
			AdminUser:            getEnv("SOUNDINBOX_ADMIN_USER", ""),
			AdminPass:            getEnv("SOUNDINBOX_ADMIN_PASS", ""),
		},
	}

	return cfg
}

// Helper functions

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}

func getEnvBool(key string, defaultValue bool) bool {
	if value := os.Getenv(key); value != "" {
		return strings.ToLower(value) == "true" || value == "1"
	}
	return defaultValue
}

func isDevelopment() bool {
	env := os.Getenv("GO_ENV")
	return env == "" || env == "development"
}
```

- [ ] **2.2** Create `.env.example` at `/Users/txeo/Git/mac/go/drolosoft/.env.example` (append if it exists):

```env
# Server
PORT=2005
HOST=
GO_ENV=development
TEMPLATE_DIR=web/templates
TEMPLATE_HOT_RELOAD=true

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

- [ ] **2.3** Create config test at `/Users/txeo/Git/mac/go/drolosoft/internal/config/config_test.go`:

```go
package config

import (
	"os"
	"testing"
)

func TestLoadDefaults(t *testing.T) {
	// Clear any env vars that might interfere
	os.Unsetenv("PORT")
	os.Unsetenv("SOUNDINBOX_DB_PATH")
	os.Unsetenv("SOUNDINBOX_MAX_ACTIVATIONS")

	cfg := Load()

	if cfg.Server.Port != "2005" {
		t.Errorf("Expected default port '2005', got %q", cfg.Server.Port)
	}

	if cfg.SoundInbox.DBPath != "data/drolosoft.db" {
		t.Errorf("Expected default DB path 'data/drolosoft.db', got %q", cfg.SoundInbox.DBPath)
	}

	if cfg.SoundInbox.MaxActivations != 3 {
		t.Errorf("Expected default max activations 3, got %d", cfg.SoundInbox.MaxActivations)
	}

	if cfg.SoundInbox.SMTPHost != "smtp.sendgrid.net" {
		t.Errorf("Expected default SMTP host 'smtp.sendgrid.net', got %q", cfg.SoundInbox.SMTPHost)
	}

	if cfg.SoundInbox.SMTPPort != 587 {
		t.Errorf("Expected default SMTP port 587, got %d", cfg.SoundInbox.SMTPPort)
	}

	if cfg.SoundInbox.SMTPFromName != "SoundInbox" {
		t.Errorf("Expected default from name 'SoundInbox', got %q", cfg.SoundInbox.SMTPFromName)
	}
}

func TestLoadFromEnv(t *testing.T) {
	os.Setenv("SOUNDINBOX_MAX_ACTIVATIONS", "5")
	os.Setenv("SOUNDINBOX_ADMIN_USER", "testadmin")
	os.Setenv("SOUNDINBOX_ADMIN_PASS", "testpass")
	defer func() {
		os.Unsetenv("SOUNDINBOX_MAX_ACTIVATIONS")
		os.Unsetenv("SOUNDINBOX_ADMIN_USER")
		os.Unsetenv("SOUNDINBOX_ADMIN_PASS")
	}()

	cfg := Load()

	if cfg.SoundInbox.MaxActivations != 5 {
		t.Errorf("Expected max activations 5, got %d", cfg.SoundInbox.MaxActivations)
	}

	if cfg.SoundInbox.AdminUser != "testadmin" {
		t.Errorf("Expected admin user 'testadmin', got %q", cfg.SoundInbox.AdminUser)
	}

	if cfg.SoundInbox.AdminPass != "testpass" {
		t.Errorf("Expected admin pass 'testpass', got %q", cfg.SoundInbox.AdminPass)
	}
}
```

### Test

```bash
cd /Users/txeo/Git/mac/go/drolosoft && go test ./internal/config/ -v
```

### Commit

```
feat(config): add SoundInbox licensing configuration fields

Add SoundInboxConfig with database, SMTP, Lemon Squeezy, admin, and
URL settings. All fields load from env vars with sensible defaults.
Add .env.example documenting all new variables.
```

---

## Task 3: Create licensing package — models

**Files:**
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/licensing/models.go`

### Steps

- [ ] **3.1** Create `/Users/txeo/Git/mac/go/drolosoft/internal/licensing/models.go`:

```go
// Package licensing provides a product-agnostic license management engine.
// It can be used with any product by configuring the table prefix (e.g., "si_" for SoundInbox,
// "cmd_" for Commando). This package handles license lifecycle, device activations, and
// order tracking.
package licensing

import (
	"errors"
	"fmt"
	"time"
)

// Status constants for licenses
const (
	LicenseStatusActive   = "active"
	LicenseStatusRevoked  = "revoked"
	LicenseStatusRefunded = "refunded"
)

// Status constants for activations
const (
	ActivationStatusActive      = "active"
	ActivationStatusDeactivated = "deactivated"
)

// Status constants for orders
const (
	OrderStatusPaid     = "paid"
	OrderStatusRefunded = "refunded"
	OrderStatusFailed   = "failed"
)

// Status constants for webhook logs
const (
	WebhookStatusReceived   = "received"
	WebhookStatusProcessing = "processing"
	WebhookStatusCompleted  = "completed"
	WebhookStatusFailed     = "failed"
)

// Sentinel errors
var (
	ErrLicenseNotFound        = errors.New("license not found")
	ErrLicenseRevoked         = errors.New("license has been revoked")
	ErrLicenseRefunded        = errors.New("license has been refunded")
	ErrActivationLimitReached = errors.New("activation limit reached")
	ErrDeviceAlreadyActivated = errors.New("device already activated")
	ErrActivationNotFound     = errors.New("activation not found")
	ErrOrderNotFound          = errors.New("order not found")
	ErrOrderDuplicate         = errors.New("order already exists")
	ErrInvalidLicenseKey      = errors.New("invalid license key format")
)

// License represents a software license.
type License struct {
	ID                 int
	LicenseKey         string
	OrderID            string
	CustomerEmail      string
	CustomerName       string
	Status             string
	MaxActivations     int
	CurrentActivations int
	CreatedAt          time.Time
	UpdatedAt          time.Time
	RevokedAt          *time.Time
	EmailSent          bool
	EmailSentAt        *time.Time
	EmailError         string
}

// IsActive returns true if the license status is "active".
func (l *License) IsActive() bool {
	return l.Status == LicenseStatusActive
}

// HasAvailableActivations returns true if the license can accept a new device.
func (l *License) HasAvailableActivations() bool {
	return l.IsActive() && l.CurrentActivations < l.MaxActivations
}

// CanDeactivate returns true if there are active activations that can be removed.
func (l *License) CanDeactivate() bool {
	return l.CurrentActivations > 0
}

// Activation represents a device activation for a license.
type Activation struct {
	ID            int
	LicenseKey    string
	DeviceID      string
	DeviceName    string
	DeviceModel   string
	OSVersion     string
	AppVersion    string
	Status        string
	ActivatedAt   time.Time
	DeactivatedAt *time.Time
	LastSeenAt    *time.Time
}

// IsActive returns true if the activation status is "active".
func (a *Activation) IsActive() bool {
	return a.Status == ActivationStatusActive
}

// Order represents a Lemon Squeezy purchase order.
type Order struct {
	ID             int
	OrderID        string
	ProductID      string
	VariantID      string
	CustomerEmail  string
	CustomerName   string
	Status         string
	TotalAmount    int // cents
	Currency       string
	EventName      string
	WebhookPayload string
	CreatedAt      time.Time
	UpdatedAt      time.Time
	RefundedAt     *time.Time
}

// TotalFormatted returns the total amount formatted with currency symbol.
func (o *Order) TotalFormatted() string {
	dollars := float64(o.TotalAmount) / 100.0
	switch o.Currency {
	case "USD":
		return fmt.Sprintf("$%.2f", dollars)
	case "EUR":
		return fmt.Sprintf("%.2f EUR", dollars)
	case "GBP":
		return fmt.Sprintf("%.2f GBP", dollars)
	default:
		return fmt.Sprintf("%.2f %s", dollars, o.Currency)
	}
}

// WebhookLog represents an entry in the webhook audit log.
type WebhookLog struct {
	ID             int
	EventName      string
	SignatureValid bool
	Payload        string
	Status         string
	ErrorMessage   string
	OrderID        string
	LicenseKey     string
	ReceivedAt     time.Time
	ProcessedAt    *time.Time
}

// DashboardStats holds aggregate statistics for the admin dashboard.
type DashboardStats struct {
	TotalLicenses    int
	ActiveLicenses   int
	RevokedLicenses  int
	RefundedLicenses int
	TotalOrders      int
	TotalRevenue     int // cents
	TotalActivations int
	UnsentEmails     int
}
```

### Test

No test file for models — these are pure data structures with trivial methods. Tests are covered by repository tests in Task 5.

### Commit

```
feat(licensing): add product-agnostic license models

Define License, Activation, Order, WebhookLog, and DashboardStats structs
with status constants and sentinel errors. Package is product-agnostic
with no table references — repository handles table prefix mapping.
```

---

## Task 4: Create licensing package — keygen

**Files:**
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/licensing/keygen.go`
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/licensing/keygen_test.go`

### Steps

- [ ] **4.1** Create `/Users/txeo/Git/mac/go/drolosoft/internal/licensing/keygen.go` (ported from Commando):

```go
package licensing

import (
	"crypto/rand"
	"fmt"
	"regexp"
	"strings"
)

const (
	// keyLength is the total number of characters in a license key (excluding hyphens).
	keyLength = 25

	// partLength is the number of characters in each key segment.
	partLength = 5

	// numParts is the number of segments in a license key.
	numParts = 5

	// Charset is the valid character set for license keys.
	// Base32 without ambiguous characters: O (oh), I (eye), L (ell), 0 (zero), 1 (one).
	Charset = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
)

var (
	// keyFormatRegex validates the license key format: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
	keyFormatRegex = regexp.MustCompile(`^[A-HJ-NP-Z2-9]{5}-[A-HJ-NP-Z2-9]{5}-[A-HJ-NP-Z2-9]{5}-[A-HJ-NP-Z2-9]{5}-[A-HJ-NP-Z2-9]{5}$`)
)

// GenerateLicenseKey generates a cryptographically secure random license key.
// Format: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX (25 characters + 4 hyphens = 29 total).
// Character set: A-Z except O, I, L and 2-9 (no 0, 1) to avoid ambiguity.
// Source: crypto/rand for cryptographic randomness.
func GenerateLicenseKey() (string, error) {
	randomBytes := make([]byte, keyLength)
	if _, err := rand.Read(randomBytes); err != nil {
		return "", fmt.Errorf("keygen: failed to generate random bytes: %w", err)
	}

	key := make([]byte, keyLength)
	charsetLen := len(Charset)
	for i := 0; i < keyLength; i++ {
		key[i] = Charset[int(randomBytes[i])%charsetLen]
	}

	return formatKey(string(key)), nil
}

// formatKey inserts hyphens into a 25-character key string.
// "ABCDEFGHIJKLMNOPQRSTUVWXY" -> "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY"
func formatKey(key string) string {
	if len(key) != keyLength {
		return key
	}

	parts := make([]string, numParts)
	for i := 0; i < numParts; i++ {
		start := i * partLength
		end := start + partLength
		parts[i] = key[start:end]
	}

	return strings.Join(parts, "-")
}

// ValidateLicenseKeyFormat validates that a license key has the correct format.
// Valid format: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX with only charset characters.
// Returns nil if valid, otherwise returns ErrInvalidLicenseKey.
func ValidateLicenseKeyFormat(key string) error {
	if len(key) != 29 { // 25 chars + 4 hyphens
		return fmt.Errorf("%w: expected 29 characters, got %d", ErrInvalidLicenseKey, len(key))
	}

	if !keyFormatRegex.MatchString(key) {
		return fmt.Errorf("%w: must be XXXXX-XXXXX-XXXXX-XXXXX-XXXXX with valid characters", ErrInvalidLicenseKey)
	}

	// Check for ambiguous characters
	keyNoHyphens := strings.ReplaceAll(key, "-", "")
	if strings.ContainsAny(keyNoHyphens, "OIL01") {
		return fmt.Errorf("%w: contains ambiguous characters (O, I, L, 0, 1)", ErrInvalidLicenseKey)
	}

	return nil
}

// NormalizeLicenseKey normalizes a license key to standard format.
// Trims whitespace, converts to uppercase, removes non-alphanumeric characters,
// and re-inserts hyphens every 5 characters.
func NormalizeLicenseKey(key string) string {
	key = strings.TrimSpace(key)
	key = strings.ToUpper(key)

	var alphanumeric strings.Builder
	for _, r := range key {
		if (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') {
			alphanumeric.WriteRune(r)
		}
	}

	cleanKey := alphanumeric.String()

	if len(cleanKey) != keyLength {
		return key // Return as-is; validation will fail later
	}

	return formatKey(cleanKey)
}
```

- [ ] **4.2** Create `/Users/txeo/Git/mac/go/drolosoft/internal/licensing/keygen_test.go`:

```go
package licensing

import (
	"strings"
	"testing"
)

func TestGenerateLicenseKey(t *testing.T) {
	key, err := GenerateLicenseKey()
	if err != nil {
		t.Fatalf("GenerateLicenseKey failed: %v", err)
	}

	if len(key) != 29 {
		t.Errorf("Expected key length 29, got %d: %s", len(key), key)
	}

	parts := strings.Split(key, "-")
	if len(parts) != 5 {
		t.Errorf("Expected 5 parts, got %d: %s", len(parts), key)
	}

	for i, part := range parts {
		if len(part) != 5 {
			t.Errorf("Part %d length: expected 5, got %d: %s", i, len(part), part)
		}
	}
}

func TestGenerateLicenseKeyUniqueness(t *testing.T) {
	seen := make(map[string]bool)
	count := 1000

	for i := 0; i < count; i++ {
		key, err := GenerateLicenseKey()
		if err != nil {
			t.Fatalf("GenerateLicenseKey failed on iteration %d: %v", i, err)
		}
		if seen[key] {
			t.Fatalf("Duplicate key generated: %s", key)
		}
		seen[key] = true
	}
}

func TestGenerateLicenseKeyCharset(t *testing.T) {
	for i := 0; i < 100; i++ {
		key, err := GenerateLicenseKey()
		if err != nil {
			t.Fatalf("GenerateLicenseKey failed: %v", err)
		}

		keyNoHyphens := strings.ReplaceAll(key, "-", "")
		for _, c := range keyNoHyphens {
			if !strings.ContainsRune(Charset, c) {
				t.Errorf("Invalid character %q in key %s", c, key)
			}
		}

		// Ensure no ambiguous characters
		if strings.ContainsAny(keyNoHyphens, "OIL01") {
			t.Errorf("Key contains ambiguous characters: %s", key)
		}
	}
}

func TestValidateLicenseKeyFormat(t *testing.T) {
	tests := []struct {
		name    string
		key     string
		wantErr bool
	}{
		{"valid key", "ABCDE-FGHJK-MNPQR-STUVW-XY234", false},
		{"too short", "ABCDE-FGHIJ", true},
		{"too long", "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY-EXTRA", true},
		{"no hyphens", "ABCDEFGHJKMNPQRSTUVWXY234", true},
		{"ambiguous O", "OABCD-EFGHJ-KMNPQ-RSTUV-WXY23", true},
		{"ambiguous I", "IABCD-EFGHJ-KMNPQ-RSTUV-WXY23", true},
		{"ambiguous L", "LABCD-EFGHJ-KMNPQ-RSTUV-WXY23", true},
		{"ambiguous 0", "0ABCD-EFGHJ-KMNPQ-RSTUV-WXY23", true},
		{"ambiguous 1", "1ABCD-EFGHJ-KMNPQ-RSTUV-WXY23", true},
		{"lowercase", "abcde-fghjk-mnpqr-stuvw-xy234", true},
		{"empty", "", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateLicenseKeyFormat(tt.key)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateLicenseKeyFormat(%q) error = %v, wantErr %v", tt.key, err, tt.wantErr)
			}
		})
	}
}

func TestValidateGeneratedKey(t *testing.T) {
	// Every generated key should pass validation
	for i := 0; i < 100; i++ {
		key, err := GenerateLicenseKey()
		if err != nil {
			t.Fatalf("GenerateLicenseKey failed: %v", err)
		}
		if err := ValidateLicenseKeyFormat(key); err != nil {
			t.Errorf("Generated key %q failed validation: %v", key, err)
		}
	}
}

func TestNormalizeLicenseKey(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected string
	}{
		{"already normalized", "ABCDE-FGHJK-MNPQR-STUVW-XY234", "ABCDE-FGHJK-MNPQR-STUVW-XY234"},
		{"lowercase", "abcde-fghjk-mnpqr-stuvw-xy234", "ABCDE-FGHJK-MNPQR-STUVW-XY234"},
		{"no hyphens", "ABCDEFGHJKMNPQRSTUVWXY234", "ABCDE-FGHJK-MNPQR-STUVW-XY234"},
		{"spaces", "  ABCDE-FGHJK-MNPQR-STUVW-XY234  ", "ABCDE-FGHJK-MNPQR-STUVW-XY234"},
		{"underscores", "ABCDE_FGHJK_MNPQR_STUVW_XY234", "ABCDE-FGHJK-MNPQR-STUVW-XY234"},
		{"mixed separators", "ABCDE FGHJK.MNPQR_STUVW-XY234", "ABCDE-FGHJK-MNPQR-STUVW-XY234"},
		{"too short returns as-is", "ABC", "ABC"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := NormalizeLicenseKey(tt.input)
			if result != tt.expected {
				t.Errorf("NormalizeLicenseKey(%q) = %q, want %q", tt.input, result, tt.expected)
			}
		})
	}
}
```

### Test

```bash
cd /Users/txeo/Git/mac/go/drolosoft && go test ./internal/licensing/ -v -run TestKeygen -run TestValidate -run TestNormalize -run TestGenerate
```

### Commit

```
feat(licensing): add license key generation and validation

Port keygen from Commando: crypto/rand generation, Base32 charset without
ambiguous chars, format validation, and normalization. Includes comprehensive
tests for uniqueness, charset validity, and edge cases.
```

---

## Task 5: Create licensing package — repository

**Files:**
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/licensing/repository.go`
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/licensing/repository_test.go`

### Steps

- [ ] **5.1** Create `/Users/txeo/Git/mac/go/drolosoft/internal/licensing/repository.go`:

```go
package licensing

import (
	"database/sql"
	"fmt"
	"strings"
	"time"
)

// Repository provides CRUD operations for the licensing tables.
// It is product-agnostic: the table prefix determines which product's data
// is accessed (e.g., "si_" for SoundInbox, "cmd_" for Commando).
type Repository struct {
	db     *sql.DB
	prefix string // table prefix, e.g. "si_"
}

// NewRepository creates a new licensing repository.
// prefix must end with underscore (e.g., "si_").
func NewRepository(db *sql.DB, prefix string) *Repository {
	if !strings.HasSuffix(prefix, "_") {
		prefix += "_"
	}
	return &Repository{db: db, prefix: prefix}
}

// table returns the full table name with prefix.
func (r *Repository) table(name string) string {
	return r.prefix + name
}

// ============================================================================
// LICENSE OPERATIONS
// ============================================================================

// CreateLicense inserts a new license record.
func (r *Repository) CreateLicense(l *License) error {
	query := fmt.Sprintf(`
		INSERT INTO %s (license_key, order_id, customer_email, customer_name, status, max_activations, current_activations)
		VALUES (?, ?, ?, ?, ?, ?, ?)`,
		r.table("licenses"))

	result, err := r.db.Exec(query,
		l.LicenseKey, l.OrderID, l.CustomerEmail, l.CustomerName,
		l.Status, l.MaxActivations, l.CurrentActivations)
	if err != nil {
		return fmt.Errorf("create license: %w", err)
	}

	id, err := result.LastInsertId()
	if err == nil {
		l.ID = int(id)
	}
	return nil
}

// GetLicenseByKey retrieves a license by its key.
func (r *Repository) GetLicenseByKey(key string) (*License, error) {
	query := fmt.Sprintf(`
		SELECT id, license_key, order_id, customer_email, customer_name,
		       status, max_activations, current_activations,
		       created_at, updated_at, revoked_at,
		       email_sent, email_sent_at, email_error
		FROM %s WHERE license_key = ?`,
		r.table("licenses"))

	l := &License{}
	var createdAt, updatedAt string
	var revokedAt, emailSentAt sql.NullString
	var customerName sql.NullString
	var emailError sql.NullString
	var emailSent int

	err := r.db.QueryRow(query, key).Scan(
		&l.ID, &l.LicenseKey, &l.OrderID, &l.CustomerEmail, &customerName,
		&l.Status, &l.MaxActivations, &l.CurrentActivations,
		&createdAt, &updatedAt, &revokedAt,
		&emailSent, &emailSentAt, &emailError,
	)
	if err == sql.ErrNoRows {
		return nil, ErrLicenseNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("get license by key: %w", err)
	}

	l.CustomerName = customerName.String
	l.EmailSent = emailSent == 1
	l.EmailError = emailError.String
	l.CreatedAt, _ = time.Parse(time.RFC3339, createdAt)
	l.UpdatedAt, _ = time.Parse(time.RFC3339, updatedAt)
	if revokedAt.Valid {
		t, _ := time.Parse(time.RFC3339, revokedAt.String)
		l.RevokedAt = &t
	}
	if emailSentAt.Valid {
		t, _ := time.Parse(time.RFC3339, emailSentAt.String)
		l.EmailSentAt = &t
	}

	return l, nil
}

// GetLicenseByOrderID retrieves a license by Lemon Squeezy order ID.
func (r *Repository) GetLicenseByOrderID(orderID string) (*License, error) {
	query := fmt.Sprintf(`
		SELECT id, license_key, order_id, customer_email, customer_name,
		       status, max_activations, current_activations,
		       created_at, updated_at, revoked_at,
		       email_sent, email_sent_at, email_error
		FROM %s WHERE order_id = ?`,
		r.table("licenses"))

	l := &License{}
	var createdAt, updatedAt string
	var revokedAt, emailSentAt sql.NullString
	var customerName sql.NullString
	var emailError sql.NullString
	var emailSent int

	err := r.db.QueryRow(query, orderID).Scan(
		&l.ID, &l.LicenseKey, &l.OrderID, &l.CustomerEmail, &customerName,
		&l.Status, &l.MaxActivations, &l.CurrentActivations,
		&createdAt, &updatedAt, &revokedAt,
		&emailSent, &emailSentAt, &emailError,
	)
	if err == sql.ErrNoRows {
		return nil, ErrLicenseNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("get license by order: %w", err)
	}

	l.CustomerName = customerName.String
	l.EmailSent = emailSent == 1
	l.EmailError = emailError.String
	l.CreatedAt, _ = time.Parse(time.RFC3339, createdAt)
	l.UpdatedAt, _ = time.Parse(time.RFC3339, updatedAt)
	if revokedAt.Valid {
		t, _ := time.Parse(time.RFC3339, revokedAt.String)
		l.RevokedAt = &t
	}
	if emailSentAt.Valid {
		t, _ := time.Parse(time.RFC3339, emailSentAt.String)
		l.EmailSentAt = &t
	}

	return l, nil
}

// UpdateLicenseStatus changes the license status (active, revoked, refunded).
func (r *Repository) UpdateLicenseStatus(key, status string) error {
	var revokedClause string
	switch status {
	case LicenseStatusRevoked:
		revokedClause = ", revoked_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"
	case LicenseStatusRefunded:
		revokedClause = ", revoked_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"
	default:
		revokedClause = ", revoked_at = NULL"
	}

	query := fmt.Sprintf(`UPDATE %s SET status = ?%s WHERE license_key = ?`,
		r.table("licenses"), revokedClause)

	result, err := r.db.Exec(query, status, key)
	if err != nil {
		return fmt.Errorf("update license status: %w", err)
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		return ErrLicenseNotFound
	}
	return nil
}

// UpdateLicenseEmailStatus records whether the license delivery email was sent.
func (r *Repository) UpdateLicenseEmailStatus(key string, sent bool, errMsg string) error {
	sentInt := 0
	if sent {
		sentInt = 1
	}

	var query string
	if sent {
		query = fmt.Sprintf(`UPDATE %s SET email_sent = ?, email_sent_at = strftime('%%Y-%%m-%%dT%%H:%%M:%%SZ', 'now'), email_error = NULL WHERE license_key = ?`,
			r.table("licenses"))
		_, err := r.db.Exec(query, sentInt, key)
		return err
	}

	query = fmt.Sprintf(`UPDATE %s SET email_sent = 0, email_error = ? WHERE license_key = ?`,
		r.table("licenses"))
	_, err := r.db.Exec(query, errMsg, key)
	return err
}

// AtomicActivate performs an atomic activation count increment.
// Uses "UPDATE ... WHERE current_activations < max_activations" to prevent race conditions.
// Returns the number of rows affected (0 = limit reached, 1 = success).
func (r *Repository) AtomicActivate(key string) (int64, error) {
	query := fmt.Sprintf(`
		UPDATE %s
		SET current_activations = current_activations + 1
		WHERE license_key = ? AND status = 'active' AND current_activations < max_activations`,
		r.table("licenses"))

	result, err := r.db.Exec(query, key)
	if err != nil {
		return 0, fmt.Errorf("atomic activate: %w", err)
	}

	return result.RowsAffected()
}

// DecrementActivationCount decrements the current activation count by 1.
func (r *Repository) DecrementActivationCount(key string) error {
	query := fmt.Sprintf(`
		UPDATE %s SET current_activations = MAX(current_activations - 1, 0)
		WHERE license_key = ?`,
		r.table("licenses"))

	_, err := r.db.Exec(query, key)
	return err
}

// GetLicensesWithPagination returns a paginated list of licenses with optional search.
func (r *Repository) GetLicensesWithPagination(limit, offset int, search string) ([]*License, int, error) {
	var countQuery, dataQuery string
	var args []interface{}

	if search != "" {
		searchLike := "%" + search + "%"
		countQuery = fmt.Sprintf(`SELECT COUNT(*) FROM %s WHERE license_key LIKE ? OR customer_email LIKE ? OR order_id LIKE ?`,
			r.table("licenses"))
		dataQuery = fmt.Sprintf(`
			SELECT id, license_key, order_id, customer_email, customer_name, status,
			       max_activations, current_activations, created_at, updated_at,
			       revoked_at, email_sent, email_sent_at, email_error
			FROM %s WHERE license_key LIKE ? OR customer_email LIKE ? OR order_id LIKE ?
			ORDER BY created_at DESC LIMIT ? OFFSET ?`,
			r.table("licenses"))
		args = []interface{}{searchLike, searchLike, searchLike}
	} else {
		countQuery = fmt.Sprintf(`SELECT COUNT(*) FROM %s`, r.table("licenses"))
		dataQuery = fmt.Sprintf(`
			SELECT id, license_key, order_id, customer_email, customer_name, status,
			       max_activations, current_activations, created_at, updated_at,
			       revoked_at, email_sent, email_sent_at, email_error
			FROM %s ORDER BY created_at DESC LIMIT ? OFFSET ?`,
			r.table("licenses"))
	}

	var total int
	if err := r.db.QueryRow(countQuery, args...).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count licenses: %w", err)
	}

	args = append(args, limit, offset)
	rows, err := r.db.Query(dataQuery, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("query licenses: %w", err)
	}
	defer rows.Close()

	var licenses []*License
	for rows.Next() {
		l := &License{}
		var createdAt, updatedAt string
		var revokedAt, emailSentAt sql.NullString
		var customerName sql.NullString
		var emailError sql.NullString
		var emailSent int

		if err := rows.Scan(
			&l.ID, &l.LicenseKey, &l.OrderID, &l.CustomerEmail, &customerName,
			&l.Status, &l.MaxActivations, &l.CurrentActivations,
			&createdAt, &updatedAt, &revokedAt,
			&emailSent, &emailSentAt, &emailError,
		); err != nil {
			return nil, 0, fmt.Errorf("scan license: %w", err)
		}

		l.CustomerName = customerName.String
		l.EmailSent = emailSent == 1
		l.EmailError = emailError.String
		l.CreatedAt, _ = time.Parse(time.RFC3339, createdAt)
		l.UpdatedAt, _ = time.Parse(time.RFC3339, updatedAt)
		if revokedAt.Valid {
			t, _ := time.Parse(time.RFC3339, revokedAt.String)
			l.RevokedAt = &t
		}
		if emailSentAt.Valid {
			t, _ := time.Parse(time.RFC3339, emailSentAt.String)
			l.EmailSentAt = &t
		}
		licenses = append(licenses, l)
	}

	return licenses, total, rows.Err()
}

// GetRecentLicenses returns the N most recently created licenses.
func (r *Repository) GetRecentLicenses(n int) ([]*License, error) {
	licenses, _, err := r.GetLicensesWithPagination(n, 0, "")
	return licenses, err
}

// GetUnsentEmails returns licenses where email delivery failed within the last hour.
func (r *Repository) GetUnsentEmails() ([]*License, error) {
	query := fmt.Sprintf(`
		SELECT id, license_key, order_id, customer_email, customer_name,
		       status, max_activations, current_activations,
		       created_at, updated_at, revoked_at,
		       email_sent, email_sent_at, email_error
		FROM %s
		WHERE email_sent = 0 AND email_error IS NOT NULL
		      AND created_at > strftime('%%Y-%%m-%%dT%%H:%%M:%%SZ', 'now', '-1 hour')
		ORDER BY created_at ASC`,
		r.table("licenses"))

	rows, err := r.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("get unsent emails: %w", err)
	}
	defer rows.Close()

	var licenses []*License
	for rows.Next() {
		l := &License{}
		var createdAt, updatedAt string
		var revokedAt, emailSentAt sql.NullString
		var customerName sql.NullString
		var emailError sql.NullString
		var emailSent int

		if err := rows.Scan(
			&l.ID, &l.LicenseKey, &l.OrderID, &l.CustomerEmail, &customerName,
			&l.Status, &l.MaxActivations, &l.CurrentActivations,
			&createdAt, &updatedAt, &revokedAt,
			&emailSent, &emailSentAt, &emailError,
		); err != nil {
			return nil, fmt.Errorf("scan unsent license: %w", err)
		}

		l.CustomerName = customerName.String
		l.EmailSent = emailSent == 1
		l.EmailError = emailError.String
		l.CreatedAt, _ = time.Parse(time.RFC3339, createdAt)
		l.UpdatedAt, _ = time.Parse(time.RFC3339, updatedAt)
		licenses = append(licenses, l)
	}

	return licenses, rows.Err()
}

// ============================================================================
// ACTIVATION OPERATIONS
// ============================================================================

// CreateActivation inserts a new device activation.
func (r *Repository) CreateActivation(a *Activation) error {
	query := fmt.Sprintf(`
		INSERT INTO %s (license_key, device_id, device_name, device_model, os_version, app_version, status)
		VALUES (?, ?, ?, ?, ?, ?, ?)`,
		r.table("activations"))

	result, err := r.db.Exec(query,
		a.LicenseKey, a.DeviceID, a.DeviceName, a.DeviceModel,
		a.OSVersion, a.AppVersion, ActivationStatusActive)
	if err != nil {
		return fmt.Errorf("create activation: %w", err)
	}

	id, err := result.LastInsertId()
	if err == nil {
		a.ID = int(id)
	}
	return nil
}

// GetActiveActivations returns all active activations for a license key.
func (r *Repository) GetActiveActivations(key string) ([]*Activation, error) {
	query := fmt.Sprintf(`
		SELECT id, license_key, device_id, device_name, device_model, os_version, app_version,
		       status, activated_at, deactivated_at, last_seen_at
		FROM %s WHERE license_key = ? AND status = 'active'
		ORDER BY activated_at ASC`,
		r.table("activations"))

	return r.scanActivations(query, key)
}

// GetAllActivations returns all activations (active and deactivated) for a license key.
func (r *Repository) GetAllActivations(key string) ([]*Activation, error) {
	query := fmt.Sprintf(`
		SELECT id, license_key, device_id, device_name, device_model, os_version, app_version,
		       status, activated_at, deactivated_at, last_seen_at
		FROM %s WHERE license_key = ?
		ORDER BY activated_at DESC`,
		r.table("activations"))

	return r.scanActivations(query, key)
}

// GetActivationByDevice returns the activation for a specific license+device combination.
func (r *Repository) GetActivationByDevice(licenseKey, deviceID string) (*Activation, error) {
	query := fmt.Sprintf(`
		SELECT id, license_key, device_id, device_name, device_model, os_version, app_version,
		       status, activated_at, deactivated_at, last_seen_at
		FROM %s WHERE license_key = ? AND device_id = ? AND status = 'active'`,
		r.table("activations"))

	a := &Activation{}
	var activatedAt string
	var deactivatedAt, lastSeenAt sql.NullString
	var deviceName, deviceModel, osVersion, appVersion sql.NullString

	err := r.db.QueryRow(query, licenseKey, deviceID).Scan(
		&a.ID, &a.LicenseKey, &a.DeviceID, &deviceName, &deviceModel,
		&osVersion, &appVersion, &a.Status, &activatedAt, &deactivatedAt, &lastSeenAt,
	)
	if err == sql.ErrNoRows {
		return nil, ErrActivationNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("get activation by device: %w", err)
	}

	a.DeviceName = deviceName.String
	a.DeviceModel = deviceModel.String
	a.OSVersion = osVersion.String
	a.AppVersion = appVersion.String
	a.ActivatedAt, _ = time.Parse(time.RFC3339, activatedAt)
	if deactivatedAt.Valid {
		t, _ := time.Parse(time.RFC3339, deactivatedAt.String)
		a.DeactivatedAt = &t
	}
	if lastSeenAt.Valid {
		t, _ := time.Parse(time.RFC3339, lastSeenAt.String)
		a.LastSeenAt = &t
	}

	return a, nil
}

// DeactivateDevice marks a specific device activation as deactivated.
func (r *Repository) DeactivateDevice(licenseKey, deviceID string) error {
	query := fmt.Sprintf(`
		UPDATE %s SET status = 'deactivated', deactivated_at = strftime('%%Y-%%m-%%dT%%H:%%M:%%SZ', 'now')
		WHERE license_key = ? AND device_id = ? AND status = 'active'`,
		r.table("activations"))

	result, err := r.db.Exec(query, licenseKey, deviceID)
	if err != nil {
		return fmt.Errorf("deactivate device: %w", err)
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		return fmt.Errorf("no active activation found for device %s on license %s", deviceID, licenseKey)
	}
	return nil
}

// DeactivateAllForLicense deactivates all active activations for a license.
func (r *Repository) DeactivateAllForLicense(licenseKey string) (int64, error) {
	query := fmt.Sprintf(`
		UPDATE %s SET status = 'deactivated', deactivated_at = strftime('%%Y-%%m-%%dT%%H:%%M:%%SZ', 'now')
		WHERE license_key = ? AND status = 'active'`,
		r.table("activations"))

	result, err := r.db.Exec(query, licenseKey)
	if err != nil {
		return 0, fmt.Errorf("deactivate all: %w", err)
	}

	return result.RowsAffected()
}

// UpdateLastSeen updates the last_seen_at timestamp for a device.
func (r *Repository) UpdateLastSeen(licenseKey, deviceID string) error {
	query := fmt.Sprintf(`
		UPDATE %s SET last_seen_at = strftime('%%Y-%%m-%%dT%%H:%%M:%%SZ', 'now')
		WHERE license_key = ? AND device_id = ? AND status = 'active'`,
		r.table("activations"))

	_, err := r.db.Exec(query, licenseKey, deviceID)
	return err
}

// scanActivations is a helper to scan activation rows.
func (r *Repository) scanActivations(query string, args ...interface{}) ([]*Activation, error) {
	rows, err := r.db.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("query activations: %w", err)
	}
	defer rows.Close()

	var activations []*Activation
	for rows.Next() {
		a := &Activation{}
		var activatedAt string
		var deactivatedAt, lastSeenAt sql.NullString
		var deviceName, deviceModel, osVersion, appVersion sql.NullString

		if err := rows.Scan(
			&a.ID, &a.LicenseKey, &a.DeviceID, &deviceName, &deviceModel,
			&osVersion, &appVersion, &a.Status, &activatedAt, &deactivatedAt, &lastSeenAt,
		); err != nil {
			return nil, fmt.Errorf("scan activation: %w", err)
		}

		a.DeviceName = deviceName.String
		a.DeviceModel = deviceModel.String
		a.OSVersion = osVersion.String
		a.AppVersion = appVersion.String
		a.ActivatedAt, _ = time.Parse(time.RFC3339, activatedAt)
		if deactivatedAt.Valid {
			t, _ := time.Parse(time.RFC3339, deactivatedAt.String)
			a.DeactivatedAt = &t
		}
		if lastSeenAt.Valid {
			t, _ := time.Parse(time.RFC3339, lastSeenAt.String)
			a.LastSeenAt = &t
		}
		activations = append(activations, a)
	}

	return activations, rows.Err()
}

// ============================================================================
// ORDER OPERATIONS
// ============================================================================

// CreateOrder inserts a new order record. Uses INSERT OR IGNORE for idempotency.
func (r *Repository) CreateOrder(o *Order) error {
	query := fmt.Sprintf(`
		INSERT OR IGNORE INTO %s (order_id, product_id, variant_id, customer_email, customer_name,
		                          status, total_amount, currency, event_name, webhook_payload)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		r.table("orders"))

	result, err := r.db.Exec(query,
		o.OrderID, o.ProductID, o.VariantID, o.CustomerEmail, o.CustomerName,
		o.Status, o.TotalAmount, o.Currency, o.EventName, o.WebhookPayload)
	if err != nil {
		return fmt.Errorf("create order: %w", err)
	}

	id, err := result.LastInsertId()
	if err == nil {
		o.ID = int(id)
	}
	return nil
}

// GetOrderByID retrieves an order by its Lemon Squeezy order ID.
func (r *Repository) GetOrderByID(orderID string) (*Order, error) {
	query := fmt.Sprintf(`
		SELECT id, order_id, product_id, variant_id, customer_email, customer_name,
		       status, total_amount, currency, event_name, webhook_payload,
		       created_at, updated_at, refunded_at
		FROM %s WHERE order_id = ?`,
		r.table("orders"))

	o := &Order{}
	var createdAt, updatedAt string
	var productID, variantID, customerName, webhookPayload, refundedAt sql.NullString

	err := r.db.QueryRow(query, orderID).Scan(
		&o.ID, &o.OrderID, &productID, &variantID, &o.CustomerEmail, &customerName,
		&o.Status, &o.TotalAmount, &o.Currency, &o.EventName, &webhookPayload,
		&createdAt, &updatedAt, &refundedAt,
	)
	if err == sql.ErrNoRows {
		return nil, ErrOrderNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("get order: %w", err)
	}

	o.ProductID = productID.String
	o.VariantID = variantID.String
	o.CustomerName = customerName.String
	o.WebhookPayload = webhookPayload.String
	o.CreatedAt, _ = time.Parse(time.RFC3339, createdAt)
	o.UpdatedAt, _ = time.Parse(time.RFC3339, updatedAt)
	if refundedAt.Valid {
		t, _ := time.Parse(time.RFC3339, refundedAt.String)
		o.RefundedAt = &t
	}

	return o, nil
}

// GetOrdersWithPagination returns a paginated list of orders.
func (r *Repository) GetOrdersWithPagination(limit, offset int) ([]*Order, int, error) {
	countQuery := fmt.Sprintf(`SELECT COUNT(*) FROM %s`, r.table("orders"))
	var total int
	if err := r.db.QueryRow(countQuery).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count orders: %w", err)
	}

	query := fmt.Sprintf(`
		SELECT id, order_id, product_id, variant_id, customer_email, customer_name,
		       status, total_amount, currency, event_name, webhook_payload,
		       created_at, updated_at, refunded_at
		FROM %s ORDER BY created_at DESC LIMIT ? OFFSET ?`,
		r.table("orders"))

	rows, err := r.db.Query(query, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("query orders: %w", err)
	}
	defer rows.Close()

	var orders []*Order
	for rows.Next() {
		o := &Order{}
		var createdAt, updatedAt string
		var productID, variantID, customerName, webhookPayload, refundedAt sql.NullString

		if err := rows.Scan(
			&o.ID, &o.OrderID, &productID, &variantID, &o.CustomerEmail, &customerName,
			&o.Status, &o.TotalAmount, &o.Currency, &o.EventName, &webhookPayload,
			&createdAt, &updatedAt, &refundedAt,
		); err != nil {
			return nil, 0, fmt.Errorf("scan order: %w", err)
		}

		o.ProductID = productID.String
		o.VariantID = variantID.String
		o.CustomerName = customerName.String
		o.WebhookPayload = webhookPayload.String
		o.CreatedAt, _ = time.Parse(time.RFC3339, createdAt)
		o.UpdatedAt, _ = time.Parse(time.RFC3339, updatedAt)
		if refundedAt.Valid {
			t, _ := time.Parse(time.RFC3339, refundedAt.String)
			o.RefundedAt = &t
		}
		orders = append(orders, o)
	}

	return orders, total, rows.Err()
}

// ============================================================================
// WEBHOOK LOG OPERATIONS
// ============================================================================

// CreateWebhookLog inserts a new webhook log entry.
func (r *Repository) CreateWebhookLog(wl *WebhookLog) error {
	query := fmt.Sprintf(`
		INSERT INTO %s (event_name, signature_valid, payload, status, order_id, license_key)
		VALUES (?, ?, ?, ?, ?, ?)`,
		r.table("webhook_logs"))

	sigValid := 0
	if wl.SignatureValid {
		sigValid = 1
	}

	result, err := r.db.Exec(query,
		wl.EventName, sigValid, wl.Payload, wl.Status, wl.OrderID, wl.LicenseKey)
	if err != nil {
		return fmt.Errorf("create webhook log: %w", err)
	}

	id, err := result.LastInsertId()
	if err == nil {
		wl.ID = int(id)
	}
	return nil
}

// UpdateWebhookLogStatus updates a webhook log entry status and metadata.
func (r *Repository) UpdateWebhookLogStatus(id int, status, errorMessage, orderID, licenseKey string) error {
	query := fmt.Sprintf(`
		UPDATE %s SET status = ?, error_message = ?, order_id = ?, license_key = ?,
		       processed_at = strftime('%%Y-%%m-%%dT%%H:%%M:%%SZ', 'now')
		WHERE id = ?`,
		r.table("webhook_logs"))

	_, err := r.db.Exec(query, status, errorMessage, orderID, licenseKey, id)
	return err
}

// GetWebhookLogsWithPagination returns a paginated list of webhook logs.
func (r *Repository) GetWebhookLogsWithPagination(limit, offset int) ([]*WebhookLog, int, error) {
	countQuery := fmt.Sprintf(`SELECT COUNT(*) FROM %s`, r.table("webhook_logs"))
	var total int
	if err := r.db.QueryRow(countQuery).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count webhook logs: %w", err)
	}

	query := fmt.Sprintf(`
		SELECT id, event_name, signature_valid, payload, status, error_message,
		       order_id, license_key, received_at, processed_at
		FROM %s ORDER BY received_at DESC LIMIT ? OFFSET ?`,
		r.table("webhook_logs"))

	rows, err := r.db.Query(query, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("query webhook logs: %w", err)
	}
	defer rows.Close()

	var logs []*WebhookLog
	for rows.Next() {
		wl := &WebhookLog{}
		var receivedAt string
		var processedAt, errorMsg, orderID, licenseKey sql.NullString
		var sigValid int

		if err := rows.Scan(
			&wl.ID, &wl.EventName, &sigValid, &wl.Payload, &wl.Status, &errorMsg,
			&orderID, &licenseKey, &receivedAt, &processedAt,
		); err != nil {
			return nil, 0, fmt.Errorf("scan webhook log: %w", err)
		}

		wl.SignatureValid = sigValid == 1
		wl.ErrorMessage = errorMsg.String
		wl.OrderID = orderID.String
		wl.LicenseKey = licenseKey.String
		wl.ReceivedAt, _ = time.Parse(time.RFC3339, receivedAt)
		if processedAt.Valid {
			t, _ := time.Parse(time.RFC3339, processedAt.String)
			wl.ProcessedAt = &t
		}
		logs = append(logs, wl)
	}

	return logs, total, rows.Err()
}

// ============================================================================
// DASHBOARD STATISTICS
// ============================================================================

// GetDashboardStats returns aggregate statistics for the admin dashboard.
func (r *Repository) GetDashboardStats() (*DashboardStats, error) {
	stats := &DashboardStats{}

	// License counts by status
	query := fmt.Sprintf(`SELECT status, COUNT(*) FROM %s GROUP BY status`, r.table("licenses"))
	rows, err := r.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("stats licenses: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var status string
		var count int
		if err := rows.Scan(&status, &count); err != nil {
			continue
		}
		stats.TotalLicenses += count
		switch status {
		case LicenseStatusActive:
			stats.ActiveLicenses = count
		case LicenseStatusRevoked:
			stats.RevokedLicenses = count
		case LicenseStatusRefunded:
			stats.RefundedLicenses = count
		}
	}

	// Total orders and revenue
	query = fmt.Sprintf(`SELECT COUNT(*), COALESCE(SUM(total_amount), 0) FROM %s WHERE status = 'paid'`, r.table("orders"))
	r.db.QueryRow(query).Scan(&stats.TotalOrders, &stats.TotalRevenue)

	// Total active activations
	query = fmt.Sprintf(`SELECT COUNT(*) FROM %s WHERE status = 'active'`, r.table("activations"))
	r.db.QueryRow(query).Scan(&stats.TotalActivations)

	// Unsent emails
	query = fmt.Sprintf(`SELECT COUNT(*) FROM %s WHERE email_sent = 0 AND email_error IS NOT NULL`, r.table("licenses"))
	r.db.QueryRow(query).Scan(&stats.UnsentEmails)

	return stats, nil
}
```

- [ ] **5.2** Create `/Users/txeo/Git/mac/go/drolosoft/internal/licensing/repository_test.go`:

```go
package licensing

import (
	"errors"
	"testing"

	"github.com/juanatsap/drolosoft/internal/database"
)

func setupTestRepo(t *testing.T) (*Repository, func()) {
	t.Helper()
	db, err := database.OpenTestDB()
	if err != nil {
		t.Fatalf("Failed to open test database: %v", err)
	}
	repo := NewRepository(db.DB, "si_")
	return repo, func() { db.Close() }
}

func TestCreateAndGetLicense(t *testing.T) {
	repo, cleanup := setupTestRepo(t)
	defer cleanup()

	lic := &License{
		LicenseKey:    "ABCDE-FGHJK-MNPQR-STUVW-XY234",
		OrderID:       "ORDER-001",
		CustomerEmail: "test@example.com",
		CustomerName:  "Test User",
		Status:        LicenseStatusActive,
		MaxActivations: 3,
	}

	if err := repo.CreateLicense(lic); err != nil {
		t.Fatalf("CreateLicense failed: %v", err)
	}

	if lic.ID == 0 {
		t.Error("Expected license ID to be set after insert")
	}

	// Get by key
	got, err := repo.GetLicenseByKey("ABCDE-FGHJK-MNPQR-STUVW-XY234")
	if err != nil {
		t.Fatalf("GetLicenseByKey failed: %v", err)
	}
	if got.CustomerEmail != "test@example.com" {
		t.Errorf("Expected email 'test@example.com', got %q", got.CustomerEmail)
	}
	if got.Status != LicenseStatusActive {
		t.Errorf("Expected status 'active', got %q", got.Status)
	}

	// Get by order
	got2, err := repo.GetLicenseByOrderID("ORDER-001")
	if err != nil {
		t.Fatalf("GetLicenseByOrderID failed: %v", err)
	}
	if got2.LicenseKey != "ABCDE-FGHJK-MNPQR-STUVW-XY234" {
		t.Errorf("Expected key 'ABCDE-FGHJK-MNPQR-STUVW-XY234', got %q", got2.LicenseKey)
	}
}

func TestGetLicenseNotFound(t *testing.T) {
	repo, cleanup := setupTestRepo(t)
	defer cleanup()

	_, err := repo.GetLicenseByKey("NONEX-ISTEN-TKEY0-00000-00000")
	if !errors.Is(err, ErrLicenseNotFound) {
		t.Errorf("Expected ErrLicenseNotFound, got %v", err)
	}
}

func TestAtomicActivate(t *testing.T) {
	repo, cleanup := setupTestRepo(t)
	defer cleanup()

	lic := &License{
		LicenseKey:    "ACTIV-ATEXX-TESTK-EYYYY-ZZZZZ",
		OrderID:       "ORDER-002",
		CustomerEmail: "test@example.com",
		Status:        LicenseStatusActive,
		MaxActivations: 2,
	}
	repo.CreateLicense(lic)

	// First activation
	rows, err := repo.AtomicActivate("ACTIV-ATEXX-TESTK-EYYYY-ZZZZZ")
	if err != nil {
		t.Fatalf("AtomicActivate failed: %v", err)
	}
	if rows != 1 {
		t.Errorf("Expected 1 row affected, got %d", rows)
	}

	// Second activation
	rows, _ = repo.AtomicActivate("ACTIV-ATEXX-TESTK-EYYYY-ZZZZZ")
	if rows != 1 {
		t.Errorf("Expected 1 row affected for second activation, got %d", rows)
	}

	// Third activation should fail (max=2)
	rows, _ = repo.AtomicActivate("ACTIV-ATEXX-TESTK-EYYYY-ZZZZZ")
	if rows != 0 {
		t.Errorf("Expected 0 rows affected (limit reached), got %d", rows)
	}
}

func TestCreateActivationAndDeactivate(t *testing.T) {
	repo, cleanup := setupTestRepo(t)
	defer cleanup()

	lic := &License{
		LicenseKey:    "DEACT-IVATE-TESTK-EYYYY-ZZZZZ",
		OrderID:       "ORDER-003",
		CustomerEmail: "test@example.com",
		Status:        LicenseStatusActive,
		MaxActivations: 3,
	}
	repo.CreateLicense(lic)

	// Create activation
	act := &Activation{
		LicenseKey:  "DEACT-IVATE-TESTK-EYYYY-ZZZZZ",
		DeviceID:    "DEVICE-001",
		DeviceName:  "Test Mac",
		DeviceModel: "MacBookPro18,1",
		OSVersion:   "15.2",
		AppVersion:  "1.0.0",
	}
	if err := repo.CreateActivation(act); err != nil {
		t.Fatalf("CreateActivation failed: %v", err)
	}

	// Get active activations
	activations, err := repo.GetActiveActivations("DEACT-IVATE-TESTK-EYYYY-ZZZZZ")
	if err != nil {
		t.Fatalf("GetActiveActivations failed: %v", err)
	}
	if len(activations) != 1 {
		t.Fatalf("Expected 1 activation, got %d", len(activations))
	}
	if activations[0].DeviceName != "Test Mac" {
		t.Errorf("Expected device name 'Test Mac', got %q", activations[0].DeviceName)
	}

	// Deactivate
	if err := repo.DeactivateDevice("DEACT-IVATE-TESTK-EYYYY-ZZZZZ", "DEVICE-001"); err != nil {
		t.Fatalf("DeactivateDevice failed: %v", err)
	}

	// Verify deactivated
	activations, _ = repo.GetActiveActivations("DEACT-IVATE-TESTK-EYYYY-ZZZZZ")
	if len(activations) != 0 {
		t.Errorf("Expected 0 active activations after deactivation, got %d", len(activations))
	}
}

func TestIdempotentReactivation(t *testing.T) {
	repo, cleanup := setupTestRepo(t)
	defer cleanup()

	lic := &License{
		LicenseKey:    "IDEMP-OTENT-TESTK-EYYYY-ZZZZZ",
		OrderID:       "ORDER-004",
		CustomerEmail: "test@example.com",
		Status:        LicenseStatusActive,
		MaxActivations: 3,
	}
	repo.CreateLicense(lic)

	act := &Activation{
		LicenseKey: "IDEMP-OTENT-TESTK-EYYYY-ZZZZZ",
		DeviceID:   "DEVICE-SAME",
		DeviceName: "Same Device",
	}
	repo.CreateActivation(act)

	// Check that the same device can be found
	found, err := repo.GetActivationByDevice("IDEMP-OTENT-TESTK-EYYYY-ZZZZZ", "DEVICE-SAME")
	if err != nil {
		t.Fatalf("GetActivationByDevice failed: %v", err)
	}
	if found.DeviceName != "Same Device" {
		t.Errorf("Expected 'Same Device', got %q", found.DeviceName)
	}
}

func TestCreateOrder(t *testing.T) {
	repo, cleanup := setupTestRepo(t)
	defer cleanup()

	order := &Order{
		OrderID:       "LS-12345",
		ProductID:     "PROD-001",
		CustomerEmail: "buyer@example.com",
		CustomerName:  "Buyer",
		Status:        OrderStatusPaid,
		TotalAmount:   1499,
		Currency:      "USD",
		EventName:     "order_created",
		WebhookPayload: `{"test": true}`,
	}

	if err := repo.CreateOrder(order); err != nil {
		t.Fatalf("CreateOrder failed: %v", err)
	}

	got, err := repo.GetOrderByID("LS-12345")
	if err != nil {
		t.Fatalf("GetOrderByID failed: %v", err)
	}
	if got.TotalAmount != 1499 {
		t.Errorf("Expected amount 1499, got %d", got.TotalAmount)
	}
	if got.TotalFormatted() != "$14.99" {
		t.Errorf("Expected '$14.99', got %q", got.TotalFormatted())
	}
}

func TestCreateOrderIdempotent(t *testing.T) {
	repo, cleanup := setupTestRepo(t)
	defer cleanup()

	order := &Order{
		OrderID:       "LS-DUP-001",
		CustomerEmail: "buyer@example.com",
		Status:        OrderStatusPaid,
		TotalAmount:   1499,
		Currency:      "USD",
		EventName:     "order_created",
	}

	// First insert
	if err := repo.CreateOrder(order); err != nil {
		t.Fatalf("First CreateOrder failed: %v", err)
	}

	// Second insert (same order_id) — should not error due to INSERT OR IGNORE
	if err := repo.CreateOrder(order); err != nil {
		t.Fatalf("Second CreateOrder should not error (idempotent): %v", err)
	}
}

func TestWebhookLog(t *testing.T) {
	repo, cleanup := setupTestRepo(t)
	defer cleanup()

	wl := &WebhookLog{
		EventName:      "order_created",
		SignatureValid: true,
		Payload:        `{"meta":{"event_name":"order_created"}}`,
		Status:         WebhookStatusReceived,
	}

	if err := repo.CreateWebhookLog(wl); err != nil {
		t.Fatalf("CreateWebhookLog failed: %v", err)
	}

	if wl.ID == 0 {
		t.Error("Expected webhook log ID to be set")
	}

	// Update status
	err := repo.UpdateWebhookLogStatus(wl.ID, WebhookStatusCompleted, "", "LS-001", "ABCDE-FGHJK-MNPQR-STUVW-XY234")
	if err != nil {
		t.Fatalf("UpdateWebhookLogStatus failed: %v", err)
	}
}

func TestDashboardStats(t *testing.T) {
	repo, cleanup := setupTestRepo(t)
	defer cleanup()

	// Create some test data
	repo.CreateLicense(&License{LicenseKey: "STATS-TEST1-AAAAA-BBBBB-CCCCC", OrderID: "O1", CustomerEmail: "a@x.com", Status: LicenseStatusActive, MaxActivations: 3})
	repo.CreateLicense(&License{LicenseKey: "STATS-TEST2-AAAAA-BBBBB-CCCCC", OrderID: "O2", CustomerEmail: "b@x.com", Status: LicenseStatusActive, MaxActivations: 3})
	repo.CreateLicense(&License{LicenseKey: "STATS-TEST3-AAAAA-BBBBB-CCCCC", OrderID: "O3", CustomerEmail: "c@x.com", Status: LicenseStatusRevoked, MaxActivations: 3})

	repo.CreateOrder(&Order{OrderID: "O1", CustomerEmail: "a@x.com", Status: OrderStatusPaid, TotalAmount: 1499, Currency: "USD", EventName: "order_created"})
	repo.CreateOrder(&Order{OrderID: "O2", CustomerEmail: "b@x.com", Status: OrderStatusPaid, TotalAmount: 1499, Currency: "USD", EventName: "order_created"})

	stats, err := repo.GetDashboardStats()
	if err != nil {
		t.Fatalf("GetDashboardStats failed: %v", err)
	}

	if stats.TotalLicenses != 3 {
		t.Errorf("Expected 3 total licenses, got %d", stats.TotalLicenses)
	}
	if stats.ActiveLicenses != 2 {
		t.Errorf("Expected 2 active licenses, got %d", stats.ActiveLicenses)
	}
	if stats.RevokedLicenses != 1 {
		t.Errorf("Expected 1 revoked license, got %d", stats.RevokedLicenses)
	}
	if stats.TotalOrders != 2 {
		t.Errorf("Expected 2 orders, got %d", stats.TotalOrders)
	}
	if stats.TotalRevenue != 2998 {
		t.Errorf("Expected revenue 2998 cents, got %d", stats.TotalRevenue)
	}
}
```

### Test

```bash
cd /Users/txeo/Git/mac/go/drolosoft && go test ./internal/licensing/ -v -run TestRepository -run TestCreate -run TestGet -run TestAtomic -run TestIdemp -run TestWebhook -run TestDashboard
```

### Commit

```
feat(licensing): add SQLite repository with full CRUD operations

Product-agnostic repository with table prefix parameter. Implements
CreateLicense, GetLicenseByKey, AtomicActivate (race-safe), device
activation/deactivation, order management, webhook logging, and
dashboard statistics. All operations tested with in-memory SQLite.
```

---

## Task 6: Create webhook verification service

**Files:**
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/services/webhook/verify.go`
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/services/webhook/models.go`
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/services/webhook/verify_test.go`

### Steps

- [ ] **6.1** Create `/Users/txeo/Git/mac/go/drolosoft/internal/services/webhook/models.go` (ported from Commando):

```go
// Package webhook provides Lemon Squeezy webhook handling with HMAC-SHA256 signature verification.
package webhook

import (
	"regexp"
)

var (
	emailRegex = regexp.MustCompile(`^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$`)
)

// LemonSqueezyWebhook represents the webhook payload from Lemon Squeezy.
type LemonSqueezyWebhook struct {
	Meta WebhookMeta `json:"meta"`
	Data WebhookData `json:"data"`
}

// WebhookMeta contains metadata about the webhook event.
type WebhookMeta struct {
	EventName  string                 `json:"event_name"`
	CustomData map[string]interface{} `json:"custom_data"`
}

// WebhookData contains the order data from the webhook.
type WebhookData struct {
	ID         string          `json:"id"`
	Type       string          `json:"type"`
	Attributes OrderAttributes `json:"attributes"`
}

// OrderAttributes contains detailed order information.
type OrderAttributes struct {
	StoreID        int     `json:"store_id"`
	CustomerID     int     `json:"customer_id"`
	Identifier     string  `json:"identifier"`
	OrderNumber    int     `json:"order_number"`
	UserName       string  `json:"user_name"`
	UserEmail      string  `json:"user_email"`
	Currency       string  `json:"currency"`
	Total          int     `json:"total"`
	TotalFormatted string  `json:"total_formatted"`
	Status         string  `json:"status"`
	Refunded       bool    `json:"refunded"`
	RefundedAt     *string `json:"refunded_at"`
	CreatedAt      string  `json:"created_at"`
	UpdatedAt      string  `json:"updated_at"`
}

// OrderInfo contains extracted order information for license generation.
type OrderInfo struct {
	OrderID       string
	CustomerName  string
	CustomerEmail string
	Total         int
	Currency      string
	Status        string
	CreatedAt     string
}

// ExtractOrderInfo extracts relevant order information from a webhook payload.
func ExtractOrderInfo(wh *LemonSqueezyWebhook) *OrderInfo {
	return &OrderInfo{
		OrderID:       wh.Data.ID,
		CustomerName:  wh.Data.Attributes.UserName,
		CustomerEmail: wh.Data.Attributes.UserEmail,
		Total:         wh.Data.Attributes.Total,
		Currency:      wh.Data.Attributes.Currency,
		Status:        wh.Data.Attributes.Status,
		CreatedAt:     wh.Data.Attributes.CreatedAt,
	}
}

// ShouldGenerateLicense returns true if a license should be generated for this webhook.
func ShouldGenerateLicense(wh *LemonSqueezyWebhook) bool {
	return wh.Meta.EventName == "order_created" &&
		wh.Data.Attributes.Status == "paid" &&
		!wh.Data.Attributes.Refunded
}

// IsRefundEvent returns true if the webhook is a refund event.
func IsRefundEvent(wh *LemonSqueezyWebhook) bool {
	return wh.Meta.EventName == "order_refunded"
}
```

- [ ] **6.2** Create `/Users/txeo/Git/mac/go/drolosoft/internal/services/webhook/verify.go`:

```go
package webhook

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
)

var (
	ErrInvalidSignature    = errors.New("invalid webhook signature")
	ErrInvalidPayload      = errors.New("invalid webhook payload")
	ErrMissingRequiredField = errors.New("missing required field")
	ErrInvalidEmail        = errors.New("invalid email format")
	ErrInvalidOrderStatus  = errors.New("order status must be 'paid'")
	ErrInvalidAmount       = errors.New("order total must be greater than zero")
)

// VerifySignature verifies the HMAC-SHA256 signature of a webhook payload.
// Uses constant-time comparison to prevent timing attacks.
func VerifySignature(payload []byte, signature string, secret string) bool {
	if signature == "" || secret == "" {
		return false
	}

	h := hmac.New(sha256.New, []byte(secret))
	h.Write(payload)
	expected := hex.EncodeToString(h.Sum(nil))

	return hmac.Equal([]byte(signature), []byte(expected))
}

// ParseWebhook parses a raw JSON payload into a LemonSqueezyWebhook struct.
func ParseWebhook(payload []byte) (*LemonSqueezyWebhook, error) {
	if len(payload) == 0 {
		return nil, fmt.Errorf("%w: empty payload", ErrInvalidPayload)
	}

	var wh LemonSqueezyWebhook
	if err := json.Unmarshal(payload, &wh); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrInvalidPayload, err)
	}

	return &wh, nil
}

// ValidatePayload validates that a webhook payload contains all required fields
// for license generation (order_created events only).
func ValidatePayload(wh *LemonSqueezyWebhook) error {
	if wh.Meta.EventName == "" {
		return fmt.Errorf("%w: event_name", ErrMissingRequiredField)
	}

	if wh.Data.Attributes.UserEmail == "" {
		return fmt.Errorf("%w: user_email", ErrMissingRequiredField)
	}

	if !emailRegex.MatchString(wh.Data.Attributes.UserEmail) {
		return fmt.Errorf("%w: %s", ErrInvalidEmail, wh.Data.Attributes.UserEmail)
	}

	// Only validate payment fields for order_created events
	if wh.Meta.EventName == "order_created" {
		if wh.Data.Attributes.Status != "paid" {
			return fmt.Errorf("%w: got '%s'", ErrInvalidOrderStatus, wh.Data.Attributes.Status)
		}

		if wh.Data.Attributes.Total <= 0 {
			return fmt.Errorf("%w: got %d", ErrInvalidAmount, wh.Data.Attributes.Total)
		}
	}

	return nil
}
```

- [ ] **6.3** Create `/Users/txeo/Git/mac/go/drolosoft/internal/services/webhook/verify_test.go`:

```go
package webhook

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"testing"
)

func computeSignature(payload, secret string) string {
	h := hmac.New(sha256.New, []byte(secret))
	h.Write([]byte(payload))
	return hex.EncodeToString(h.Sum(nil))
}

func TestVerifySignature(t *testing.T) {
	secret := "test-webhook-secret"
	payload := `{"meta":{"event_name":"order_created"},"data":{"id":"123"}}`

	validSig := computeSignature(payload, secret)

	tests := []struct {
		name      string
		payload   string
		signature string
		secret    string
		want      bool
	}{
		{"valid signature", payload, validSig, secret, true},
		{"wrong signature", payload, "deadbeef", secret, false},
		{"wrong secret", payload, validSig, "wrong-secret", false},
		{"empty signature", payload, "", secret, false},
		{"empty secret", payload, validSig, "", false},
		{"tampered payload", payload + "x", validSig, secret, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := VerifySignature([]byte(tt.payload), tt.signature, tt.secret)
			if got != tt.want {
				t.Errorf("VerifySignature() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestParseWebhook(t *testing.T) {
	validPayload := `{
		"meta": {"event_name": "order_created"},
		"data": {
			"id": "12345",
			"type": "orders",
			"attributes": {
				"user_name": "Test User",
				"user_email": "test@example.com",
				"currency": "USD",
				"total": 1499,
				"total_formatted": "$14.99",
				"status": "paid",
				"created_at": "2026-04-20T10:00:00Z"
			}
		}
	}`

	wh, err := ParseWebhook([]byte(validPayload))
	if err != nil {
		t.Fatalf("ParseWebhook failed: %v", err)
	}

	if wh.Meta.EventName != "order_created" {
		t.Errorf("Expected event 'order_created', got %q", wh.Meta.EventName)
	}
	if wh.Data.Attributes.UserEmail != "test@example.com" {
		t.Errorf("Expected email 'test@example.com', got %q", wh.Data.Attributes.UserEmail)
	}
	if wh.Data.Attributes.Total != 1499 {
		t.Errorf("Expected total 1499, got %d", wh.Data.Attributes.Total)
	}

	// Empty payload
	_, err = ParseWebhook([]byte{})
	if err == nil {
		t.Error("Expected error for empty payload")
	}

	// Invalid JSON
	_, err = ParseWebhook([]byte("not json"))
	if err == nil {
		t.Error("Expected error for invalid JSON")
	}
}

func TestValidatePayload(t *testing.T) {
	valid := &LemonSqueezyWebhook{
		Meta: WebhookMeta{EventName: "order_created"},
		Data: WebhookData{
			Attributes: OrderAttributes{
				UserEmail: "test@example.com",
				Status:    "paid",
				Total:     1499,
			},
		},
	}

	if err := ValidatePayload(valid); err != nil {
		t.Errorf("Expected valid payload, got error: %v", err)
	}

	// Missing email
	noEmail := &LemonSqueezyWebhook{
		Meta: WebhookMeta{EventName: "order_created"},
		Data: WebhookData{Attributes: OrderAttributes{Status: "paid", Total: 1499}},
	}
	if err := ValidatePayload(noEmail); err == nil {
		t.Error("Expected error for missing email")
	}

	// Unpaid status
	unpaid := &LemonSqueezyWebhook{
		Meta: WebhookMeta{EventName: "order_created"},
		Data: WebhookData{Attributes: OrderAttributes{UserEmail: "test@example.com", Status: "pending", Total: 1499}},
	}
	if err := ValidatePayload(unpaid); err == nil {
		t.Error("Expected error for unpaid status")
	}

	// Zero amount
	zeroAmount := &LemonSqueezyWebhook{
		Meta: WebhookMeta{EventName: "order_created"},
		Data: WebhookData{Attributes: OrderAttributes{UserEmail: "test@example.com", Status: "paid", Total: 0}},
	}
	if err := ValidatePayload(zeroAmount); err == nil {
		t.Error("Expected error for zero amount")
	}
}

func TestShouldGenerateLicense(t *testing.T) {
	// Should generate
	paid := &LemonSqueezyWebhook{
		Meta: WebhookMeta{EventName: "order_created"},
		Data: WebhookData{Attributes: OrderAttributes{Status: "paid", Refunded: false}},
	}
	if !ShouldGenerateLicense(paid) {
		t.Error("Expected ShouldGenerateLicense=true for paid order_created")
	}

	// Refunded order
	refunded := &LemonSqueezyWebhook{
		Meta: WebhookMeta{EventName: "order_created"},
		Data: WebhookData{Attributes: OrderAttributes{Status: "paid", Refunded: true}},
	}
	if ShouldGenerateLicense(refunded) {
		t.Error("Expected ShouldGenerateLicense=false for refunded order")
	}

	// Refund event
	refundEvent := &LemonSqueezyWebhook{
		Meta: WebhookMeta{EventName: "order_refunded"},
	}
	if ShouldGenerateLicense(refundEvent) {
		t.Error("Expected ShouldGenerateLicense=false for order_refunded event")
	}
	if !IsRefundEvent(refundEvent) {
		t.Error("Expected IsRefundEvent=true for order_refunded")
	}
}

func TestExtractOrderInfo(t *testing.T) {
	wh := &LemonSqueezyWebhook{
		Data: WebhookData{
			ID: "ORDER-999",
			Attributes: OrderAttributes{
				UserName:  "John Doe",
				UserEmail: "john@example.com",
				Total:     1499,
				Currency:  "USD",
				Status:    "paid",
				CreatedAt: "2026-04-20T10:00:00Z",
			},
		},
	}

	info := ExtractOrderInfo(wh)
	if info.OrderID != "ORDER-999" {
		t.Errorf("Expected OrderID 'ORDER-999', got %q", info.OrderID)
	}
	if info.CustomerName != "John Doe" {
		t.Errorf("Expected name 'John Doe', got %q", info.CustomerName)
	}
	if info.Total != 1499 {
		t.Errorf("Expected total 1499, got %d", info.Total)
	}
}
```

### Test

```bash
cd /Users/txeo/Git/mac/go/drolosoft && go test ./internal/services/webhook/ -v
```

### Commit

```
feat(webhook): add Lemon Squeezy webhook verification and parsing

Port HMAC-SHA256 signature verification from Commando with constant-time
comparison. Parse and validate webhook payloads for order_created and
order_refunded events. Full test coverage for signatures, parsing, and
validation edge cases.
```

---

## Task 7: Create email service

**Files:**
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/services/email/email.go`
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/services/email/templates_soundinbox.go`
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/services/email/email_test.go`

### Steps

- [ ] **7.1** Create `/Users/txeo/Git/mac/go/drolosoft/internal/services/email/email.go` (ported from Commando, rebranded):

```go
// Package email provides SMTP email delivery with retry logic for license key distribution.
package email

import (
	"fmt"
	"log"
	"net/smtp"
	"net/url"
	"regexp"
	"strings"
	"time"
)

var (
	htmlTagRegex    = regexp.MustCompile(`<[^>]*>`)
	whitespaceRegex = regexp.MustCompile(`\s+`)
	linkRegex       = regexp.MustCompile(`<a[^>]+href=["']([^"']+)["'][^>]*>([^<]+)</a>`)
)

// SMTPConfig holds SMTP server configuration.
type SMTPConfig struct {
	Host      string
	Port      int
	Username  string
	Password  string
	FromName  string
	FromEmail string
}

// EmailService handles email delivery operations.
type EmailService struct {
	config *SMTPConfig
}

// LicenseEmailData contains data for the license delivery email template.
type LicenseEmailData struct {
	CustomerName  string
	LicenseKey    string
	OrderID       string
	PurchaseDate  string
	Amount        string
	SupportEmail  string
	DownloadURL   string
	ActivationURL string
}

// NewEmailService creates a new email service.
func NewEmailService(cfg *SMTPConfig) *EmailService {
	return &EmailService{config: cfg}
}

// SendLicenseEmail sends a license key delivery email with retry logic.
// Retries up to 3 times with 5-second exponential backoff.
func (s *EmailService) SendLicenseEmail(to string, data *LicenseEmailData) error {
	if err := validateEmailData(data); err != nil {
		return fmt.Errorf("invalid email data: %w", err)
	}

	htmlBody := renderSoundInboxLicenseHTML(data)
	textBody := htmlToPlainText(htmlBody)

	email := &emailMessage{
		To:       to,
		From:     fmt.Sprintf("%s <%s>", s.config.FromName, s.config.FromEmail),
		Subject:  "Your SoundInbox Pro License Key",
		HTMLBody: htmlBody,
		TextBody: textBody,
	}

	// Retry loop: 3 attempts with exponential backoff
	var lastErr error
	for attempt := 1; attempt <= 3; attempt++ {
		if err := s.sendSMTP(email); err != nil {
			lastErr = err
			log.Printf("[email] Attempt %d/3 failed for %s: %v", attempt, to, err)
			if attempt < 3 {
				backoff := time.Duration(attempt*5) * time.Second
				time.Sleep(backoff)
			}
			continue
		}
		log.Printf("[email] License email sent to %s (attempt %d)", to, attempt)
		return nil
	}

	return fmt.Errorf("email delivery failed after 3 attempts: %w", lastErr)
}

type emailMessage struct {
	To       string
	From     string
	Subject  string
	HTMLBody string
	TextBody string
}

func (s *EmailService) sendSMTP(msg *emailMessage) error {
	boundary := "boundary-drolosoft-soundinbox"

	var message strings.Builder

	// Headers
	message.WriteString(fmt.Sprintf("From: %s\r\n", msg.From))
	message.WriteString(fmt.Sprintf("To: %s\r\n", msg.To))
	message.WriteString(fmt.Sprintf("Subject: %s\r\n", msg.Subject))
	message.WriteString("MIME-Version: 1.0\r\n")
	message.WriteString(fmt.Sprintf("Content-Type: multipart/alternative; boundary=\"%s\"\r\n", boundary))
	message.WriteString("\r\n")

	// Plain text part
	message.WriteString(fmt.Sprintf("--%s\r\n", boundary))
	message.WriteString("Content-Type: text/plain; charset=\"UTF-8\"\r\n\r\n")
	message.WriteString(msg.TextBody)
	message.WriteString("\r\n\r\n")

	// HTML part
	message.WriteString(fmt.Sprintf("--%s\r\n", boundary))
	message.WriteString("Content-Type: text/html; charset=\"UTF-8\"\r\n\r\n")
	message.WriteString(msg.HTMLBody)
	message.WriteString("\r\n\r\n")

	// Close boundary
	message.WriteString(fmt.Sprintf("--%s--\r\n", boundary))

	auth := smtp.PlainAuth("", s.config.Username, s.config.Password, s.config.Host)
	addr := fmt.Sprintf("%s:%d", s.config.Host, s.config.Port)

	return smtp.SendMail(addr, auth, s.config.FromEmail, []string{msg.To}, []byte(message.String()))
}

func htmlToPlainText(html string) string {
	text := linkRegex.ReplaceAllString(html, "$2 ($1)")
	text = htmlTagRegex.ReplaceAllString(text, "")
	text = strings.ReplaceAll(text, "&nbsp;", " ")
	text = strings.ReplaceAll(text, "&amp;", "&")
	text = strings.ReplaceAll(text, "&lt;", "<")
	text = strings.ReplaceAll(text, "&gt;", ">")
	text = strings.ReplaceAll(text, "&quot;", "\"")
	text = whitespaceRegex.ReplaceAllString(text, " ")

	lines := strings.Split(text, "\n")
	for i, line := range lines {
		lines[i] = strings.TrimSpace(line)
	}
	return strings.TrimSpace(strings.Join(lines, "\n"))
}

func validateEmailData(data *LicenseEmailData) error {
	if data.CustomerName == "" {
		return fmt.Errorf("CustomerName is required")
	}
	if data.LicenseKey == "" {
		return fmt.Errorf("LicenseKey is required")
	}
	if data.OrderID == "" {
		return fmt.Errorf("OrderID is required")
	}
	if data.PurchaseDate == "" {
		return fmt.Errorf("PurchaseDate is required")
	}
	if data.Amount == "" {
		return fmt.Errorf("Amount is required")
	}
	if data.SupportEmail == "" {
		return fmt.Errorf("SupportEmail is required")
	}
	if data.DownloadURL != "" {
		if u, err := url.Parse(data.DownloadURL); err != nil || u.Scheme == "" {
			return fmt.Errorf("DownloadURL must be a valid URL")
		}
	}
	return nil
}
```

- [ ] **7.2** Create `/Users/txeo/Git/mac/go/drolosoft/internal/services/email/templates_soundinbox.go` with the SoundInbox-branded HTML template (orange/amber theme). This is a long HTML template string — create the file with the complete template similar to Commando's but rebranded for SoundInbox with orange/amber colors, "SoundInbox Pro" product name, "3 devices" activation limit, and `drolosoft.com/soundinbox` URLs.

```go
package email

import (
	"bytes"
	"fmt"
	"html/template"
)

// renderSoundInboxLicenseHTML generates the SoundInbox-branded HTML license email.
func renderSoundInboxLicenseHTML(data *LicenseEmailData) string {
	tmpl := `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your SoundInbox Pro License</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f4f0;
        }
        .container {
            background-color: #ffffff;
            border-radius: 8px;
            padding: 40px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #b45309;
            margin: 0 0 10px 0;
            font-size: 28px;
        }
        .license-key {
            background-color: #fffbeb;
            border: 2px solid #f59e0b;
            border-radius: 6px;
            padding: 20px;
            margin: 30px 0;
            text-align: center;
        }
        .license-key-label {
            font-size: 14px;
            color: #92400e;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .license-key-value {
            font-size: 24px;
            font-weight: bold;
            color: #b45309;
            font-family: "Courier New", Courier, monospace;
            letter-spacing: 2px;
            word-break: break-all;
        }
        .button {
            display: inline-block;
            padding: 12px 24px;
            margin: 10px 5px;
            background-color: #f59e0b;
            color: #ffffff !important;
            text-decoration: none;
            border-radius: 5px;
            font-weight: 500;
        }
        .button-secondary {
            background-color: #78716c;
        }
        .section { margin: 30px 0; }
        .section-title {
            font-size: 18px;
            color: #b45309;
            margin-bottom: 15px;
            font-weight: 600;
        }
        .details-table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        .details-table td { padding: 10px; border-bottom: 1px solid #e9ecef; }
        .details-table td:first-child { font-weight: 600; color: #6c757d; width: 40%; }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e9ecef;
            text-align: center;
            color: #6c757d;
            font-size: 14px;
        }
        .support-link { color: #f59e0b; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Thank You for Your Purchase!</h1>
            <p>Your SoundInbox Pro License Key</p>
        </div>
        <div style="font-size: 16px; margin-bottom: 20px;">
            <p>Hi {{.CustomerName}},</p>
            <p>Thank you for purchasing SoundInbox Pro! Your license key is ready. You can now monitor up to 5 email accounts with custom sound alerts.</p>
        </div>
        <div class="license-key">
            <div class="license-key-label">Your License Key</div>
            <div class="license-key-value">{{.LicenseKey}}</div>
        </div>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{{.DownloadURL}}" class="button">Download SoundInbox</a>
            <a href="{{.ActivationURL}}" class="button button-secondary">Activation Instructions</a>
        </div>
        <div class="section">
            <div class="section-title">Order Details</div>
            <table class="details-table">
                <tr><td>Order ID</td><td>{{.OrderID}}</td></tr>
                <tr><td>Purchase Date</td><td>{{.PurchaseDate}}</td></tr>
                <tr><td>Amount</td><td>{{.Amount}}</td></tr>
                <tr><td>License Type</td><td>SoundInbox Pro (3 devices)</td></tr>
            </table>
        </div>
        <div class="section">
            <div class="section-title">Quick Start Guide</div>
            <ol style="margin: 10px 0; padding-left: 20px;">
                <li>Download SoundInbox from the button above (or via Homebrew)</li>
                <li>Open SoundInbox from the menu bar</li>
                <li>Go to Settings &gt; License</li>
                <li>Enter your license key and click Activate</li>
            </ol>
        </div>
        <div class="section">
            <div class="section-title">Need Help?</div>
            <p>Email: <a href="mailto:{{.SupportEmail}}" class="support-link">{{.SupportEmail}}</a></p>
            <p>Response time: 24-48 hours</p>
        </div>
        <div class="footer">
            <p><strong>Important:</strong> Keep your license key safe. You can activate SoundInbox Pro on up to 3 devices.</p>
            <p style="margin-top: 15px;">Drolosoft &mdash; drolosoft.com</p>
        </div>
    </div>
</body>
</html>`

	t := template.Must(template.New("soundinbox-license").Parse(tmpl))
	var buf bytes.Buffer
	if err := t.Execute(&buf, data); err != nil {
		return fmt.Sprintf("<html><body><h1>Your License Key</h1><p>%s</p></body></html>", data.LicenseKey)
	}
	return buf.String()
}
```

- [ ] **7.3** Create `/Users/txeo/Git/mac/go/drolosoft/internal/services/email/email_test.go`:

```go
package email

import (
	"strings"
	"testing"
)

func TestRenderSoundInboxLicenseHTML(t *testing.T) {
	data := &LicenseEmailData{
		CustomerName:  "Test User",
		LicenseKey:    "ABCDE-FGHJK-MNPQR-STUVW-XY234",
		OrderID:       "ORDER-001",
		PurchaseDate:  "April 20, 2026",
		Amount:        "$14.99",
		SupportEmail:  "support@drolosoft.com",
		DownloadURL:   "https://drolosoft.com/soundinbox/download",
		ActivationURL: "https://drolosoft.com/soundinbox/download#activation",
	}

	html := renderSoundInboxLicenseHTML(data)

	// Verify key elements are present
	checks := []string{
		"SoundInbox Pro",
		"ABCDE-FGHJK-MNPQR-STUVW-XY234",
		"Test User",
		"ORDER-001",
		"$14.99",
		"support@drolosoft.com",
		"3 devices",
		"drolosoft.com/soundinbox/download",
	}

	for _, check := range checks {
		if !strings.Contains(html, check) {
			t.Errorf("HTML template missing expected content: %q", check)
		}
	}
}

func TestHtmlToPlainText(t *testing.T) {
	html := `<h1>Title</h1><p>Hello <a href="https://example.com">World</a></p>`
	text := htmlToPlainText(html)

	if strings.Contains(text, "<") {
		t.Error("Plain text should not contain HTML tags")
	}
	if !strings.Contains(text, "World (https://example.com)") {
		t.Errorf("Expected link extraction, got: %s", text)
	}
}

func TestValidateEmailData(t *testing.T) {
	valid := &LicenseEmailData{
		CustomerName: "Test",
		LicenseKey:   "KEY",
		OrderID:      "ORDER",
		PurchaseDate: "Date",
		Amount:       "$14.99",
		SupportEmail: "support@test.com",
	}

	if err := validateEmailData(valid); err != nil {
		t.Errorf("Expected valid data, got error: %v", err)
	}

	// Missing customer name
	invalid := &LicenseEmailData{
		LicenseKey:   "KEY",
		OrderID:      "ORDER",
		PurchaseDate: "Date",
		Amount:       "$14.99",
		SupportEmail: "support@test.com",
	}
	if err := validateEmailData(invalid); err == nil {
		t.Error("Expected error for missing CustomerName")
	}
}
```

### Test

```bash
cd /Users/txeo/Git/mac/go/drolosoft && go test ./internal/services/email/ -v
```

### Commit

```
feat(email): add SMTP email service with SoundInbox-branded template

Port email delivery from Commando with 3-attempt retry and exponential
backoff. Create SoundInbox-branded HTML template with orange/amber theme.
Include multipart MIME (HTML + plain text) and input validation.
```

---

## Task 8: Create API handlers

**Files:**
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/handlers/soundinbox_api.go`
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/handlers/soundinbox_api_test.go`

### Steps

- [ ] **8.1** Create `/Users/txeo/Git/mac/go/drolosoft/internal/handlers/soundinbox_api.go` with handlers for ValidateLicense, ActivateLicense, DeactivateLicense, GetLicense, and HealthCheck. Each handler must:
  - Check `r.Method` and return 405 for wrong methods
  - Parse JSON request body
  - Normalize and validate license key format
  - Perform database operations via the licensing repository
  - Return JSON responses with correct HTTP status codes
  - Include `server_time` and `features.max_accounts` in validate/activate responses
  - Use atomic SQL for activation (call `repo.AtomicActivate`)
  - Handle idempotent re-activation (same device returns 200, not 201)
  - Validate `device_name`/`device_model` (max 100 chars, no control characters)
  - Return active device list when activation limit is reached (403)

The handler struct should be:

```go
type SoundInboxAPIHandler struct {
    repo           *licensing.Repository
    db             *database.DB
    maxActivations int
}
```

With constructor `NewSoundInboxAPIHandler(db *database.DB, maxActivations int)`.

- [ ] **8.2** Create `/Users/txeo/Git/mac/go/drolosoft/internal/handlers/soundinbox_api_test.go` using `httptest.NewRecorder()` and `httptest.NewRequest()`. Test each endpoint:
  - Validate: format error (400), not found (404), active license (200), revoked license (200 with valid=false)
  - Activate: success (201), already activated same device (200), limit reached (403), bad format (400)
  - Deactivate: success (200), not found (404)
  - Health: returns 200 with DB status

### Test

```bash
cd /Users/txeo/Git/mac/go/drolosoft && go test ./internal/handlers/ -v -run TestSoundInbox
```

### Commit

```
feat(api): add SoundInbox license API handlers

Implement validate, activate, deactivate, get-license, and health check
endpoints. Uses atomic SQL for race-safe activation counting, idempotent
re-activation, input sanitization, and correct HTTP status codes per spec.
```

---

## Task 9: Create webhook handler

**Files:**
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/handlers/soundinbox_webhook.go`
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/handlers/soundinbox_webhook_test.go`

### Steps

- [ ] **9.1** Create webhook handler that:
  - Accepts POST only (405 otherwise)
  - Reads `X-Signature` header; returns 401 with empty body if missing/invalid
  - Reads raw body
  - Verifies HMAC signature; returns 401 with empty body if invalid
  - Parses payload
  - Responds 200 `{"status":"accepted"}` immediately
  - Processes asynchronously via buffered channel (capacity 100)
  - Goroutine wraps processing in `defer/recover` for panic safety
  - Idempotency: checks if license already exists for this order_id before generating
  - On `order_created`: store order, generate key, store license, send email
  - On `order_refunded`: revoke license, deactivate all devices
  - Logs all activity to webhook_logs table

The handler struct needs access to the email service configuration (SMTPConfig fields from config).

- [ ] **9.2** Create test with mock webhook payloads verifying:
  - Valid signature is accepted (200)
  - Invalid signature is rejected (401 with empty body)
  - Missing signature is rejected (401)
  - order_created processing creates license in DB
  - Duplicate order_id is idempotent
  - order_refunded revokes license

### Test

```bash
cd /Users/txeo/Git/mac/go/drolosoft && go test ./internal/handlers/ -v -run TestWebhook
```

### Commit

```
feat(webhook): add Lemon Squeezy webhook handler with async processing

Verify HMAC signatures, respond 200 immediately, process order_created
and order_refunded events asynchronously. Uses buffered channel for
bounded concurrency, defer/recover for panic safety, and idempotency
check before license generation.
```

---

## Task 10: Create middleware

**Files:**
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/middleware/basicauth.go`
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/middleware/cors.go`
- Modify: `/Users/txeo/Git/mac/go/drolosoft/internal/middleware/ratelimit.go` (add sliding window variant and cleanup goroutine from Commando)
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/middleware/middleware_test.go`

### Steps

- [ ] **10.1** Create `basicauth.go` with `BasicAuth(username, password string) func(http.Handler) http.Handler`. Uses `crypto/subtle.ConstantTimeCompare`. Returns 503 if credentials not configured (empty username/password). Sets `WWW-Authenticate: Basic realm="Admin Dashboard"` on 401.

- [ ] **10.2** Create `cors.go` with `CORS(allowedOrigins ...string) func(http.Handler) http.Handler`. Checks `Origin` header against allowed list. If no `Origin` header (native app), allows the request. Sets `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods`, `Access-Control-Allow-Headers`.

- [ ] **10.3** Enhance `ratelimit.go`: Port Commando's sliding window rate limiter with background cleanup goroutine. Add `NewAPIRateLimiter()` (60/min), `NewWebhookRateLimiter()` (100/min). Keep existing token bucket as `DefaultRateLimiter()`.

- [ ] **10.4** Create tests for BasicAuth (valid/invalid creds, missing creds), CORS (allowed origin, disallowed origin, no origin), and rate limiting.

### Test

```bash
cd /Users/txeo/Git/mac/go/drolosoft && go test ./internal/middleware/ -v
```

### Commit

```
feat(middleware): add Basic Auth, CORS, and sliding window rate limiter

Add BasicAuth with constant-time comparison for admin routes.
Add CORS origin checking for API endpoints (allows no-origin for native apps).
Port Commando's sliding window rate limiter with cleanup goroutine.
```

---

## Task 11: Create web page handlers + templates

**Files:**
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/handlers/soundinbox_pages.go`
- Create: `/Users/txeo/Git/mac/go/drolosoft/web/templates/site/pages/soundinbox/pricing.html`
- Create: `/Users/txeo/Git/mac/go/drolosoft/web/templates/site/pages/soundinbox/download.html`
- Create: `/Users/txeo/Git/mac/go/drolosoft/web/templates/site/pages/soundinbox/privacy.html`
- Create: `/Users/txeo/Git/mac/go/drolosoft/web/templates/site/pages/soundinbox/changelog.html`

### Steps

- [ ] **11.1** Create handler file with methods `Pricing`, `Download`, `Privacy`, `Changelog` on a `SoundInboxPageHandler` struct that holds reference to `SiteHandler` for template rendering. Each method calls `renderPage` with the appropriate template path and `pageOpts`.

- [ ] **11.2** Create the **privacy page FIRST** (OAuth blocker). Must include:
  - What data SoundInbox accesses (Gmail metadata only)
  - How data is used (local pattern matching, no cloud)
  - Data storage (macOS Keychain, no cloud)
  - Third-party sharing (none)
  - Data retention (local, user clearable)
  - User rights (revoke via Google Account)
  - Google API Services User Data Policy compliance
  - Limited Use disclosure
  - Contact: support@drolosoft.com
  - Last updated date

- [ ] **11.3** Create pricing page with Free vs Pro comparison. "Buy Now" button links to `{{.CheckoutURL}}` (from config). Free column emphasizes completeness, Pro column emphasizes multi-account support.

- [ ] **11.4** Create download page with Homebrew and DMG instructions, activation guide. Handle `?purchased=true` query parameter for post-purchase state.

- [ ] **11.5** Create changelog page with version history (can start with v1.0.0 placeholder).

### Test

```bash
cd /Users/txeo/Git/mac/go/drolosoft && go test ./internal/handlers/ -v -run TestSoundInboxPages
```

### Commit

```
feat(pages): add SoundInbox web pages — privacy, pricing, download, changelog

Privacy page compliant with Google API Services User Data Policy (OAuth blocker).
Pricing page with Free vs Pro comparison. Download page with Homebrew/DMG
instructions and post-purchase state. Changelog page for version history.
```

---

## Task 12: Create admin dashboard handlers + templates

**Files:**
- Create: `/Users/txeo/Git/mac/go/drolosoft/internal/handlers/soundinbox_admin.go`
- Create: `/Users/txeo/Git/mac/go/drolosoft/web/templates/admin/soundinbox/dashboard.html`
- Create: `/Users/txeo/Git/mac/go/drolosoft/web/templates/admin/soundinbox/licenses.html`
- Create: `/Users/txeo/Git/mac/go/drolosoft/web/templates/admin/soundinbox/license-detail.html`
- Create: `/Users/txeo/Git/mac/go/drolosoft/web/templates/admin/soundinbox/orders.html`
- Create: `/Users/txeo/Git/mac/go/drolosoft/web/templates/admin/soundinbox/webhooks.html`
- Create: `/Users/txeo/Git/mac/go/drolosoft/web/templates/admin/soundinbox/generate.html`

### Steps

- [ ] **12.1** Create `SoundInboxAdminHandler` struct with methods: `Dashboard`, `LicenseList`, `LicenseDetail`, `GenerateLicense` (GET form + POST submit), `RevokeLicense`, `ResendEmail`, `OrderList`, `WebhookLogs`. Port patterns from Commando's admin handlers.

- [ ] **12.2** Create admin templates. Dashboard shows: total licenses, active licenses, revenue, recent licenses, unsent email alerts. License list with search and pagination. License detail with activation list, revoke button, resend email button. Generate form with email, name, reason fields.

- [ ] **12.3** Admin routes will be protected by BasicAuth middleware (wired in Task 13). No client-side JS — server-rendered HTML only.

### Test

```bash
cd /Users/txeo/Git/mac/go/drolosoft && go test ./internal/handlers/ -v -run TestAdmin
```

### Commit

```
feat(admin): add SoundInbox admin dashboard with license management

Server-rendered admin panel: dashboard stats, license list/detail,
manual generation, revoke, email resend, order list, webhook logs.
Protected by Basic Auth middleware. No client-side JavaScript.
```

---

## Task 13: Wire everything in main.go

**Files:**
- Modify: `/Users/txeo/Git/mac/go/drolosoft/cmd/server/main.go`

### Steps

- [ ] **13.1** In `main()`, after config load, initialize the database:

```go
// Initialize SQLite database
db, err := database.Open(cfg.SoundInbox.DBPath)
if err != nil {
    log.Fatalf("Failed to open database: %v", err)
}
defer db.Close()

// Run migrations
if err := db.Migrate(); err != nil {
    log.Fatalf("Failed to run migrations: %v", err)
}
```

- [ ] **13.2** Create the licensing repository, email service, and all handlers:

```go
repo := licensing.NewRepository(db.DB, "si_")

soundinboxAPI := handlers.NewSoundInboxAPIHandler(db, cfg.SoundInbox.MaxActivations)
soundinboxWebhook := handlers.NewSoundInboxWebhookHandler(db, repo, &cfg.SoundInbox)
soundinboxPages := handlers.NewSoundInboxPageHandler(siteHandler, &cfg.SoundInbox)
soundinboxAdmin := handlers.NewSoundInboxAdminHandler(db, repo, &cfg.SoundInbox)
```

- [ ] **13.3** Create rate limiters and middleware:

```go
apiLimiter := middleware.NewRateLimiter(60, time.Minute)
webhookLimiter := middleware.NewRateLimiter(100, time.Minute)
defer apiLimiter.Stop()
defer webhookLimiter.Stop()
```

- [ ] **13.4** Register all new routes:

```go
// SoundInbox pages
mux.HandleFunc("/soundinbox/pricing", soundinboxPages.Pricing)
mux.HandleFunc("/soundinbox/download", soundinboxPages.Download)
mux.HandleFunc("/soundinbox/privacy", soundinboxPages.Privacy)
mux.HandleFunc("/soundinbox/changelog", soundinboxPages.Changelog)

// SoundInbox License API (rate limited)
apiMux := http.NewServeMux()
apiMux.HandleFunc("/api/soundinbox/licenses/validate", soundinboxAPI.ValidateLicense)
apiMux.HandleFunc("/api/soundinbox/licenses/activate", soundinboxAPI.ActivateLicense)
apiMux.HandleFunc("/api/soundinbox/licenses/deactivate", soundinboxAPI.DeactivateLicense)
apiMux.HandleFunc("/api/soundinbox/licenses/", soundinboxAPI.GetLicense)
apiMux.HandleFunc("/api/soundinbox/health", soundinboxAPI.HealthCheck)
mux.Handle("/api/soundinbox/", middleware.RateLimit(apiLimiter)(
    middleware.CORS("https://drolosoft.com")(apiMux)))

// Webhook (separate rate limit)
mux.Handle("/api/soundinbox/webhooks/", middleware.RateLimit(webhookLimiter)(
    http.HandlerFunc(soundinboxWebhook.Handle)))

// Admin panel (Basic Auth protected)
adminMux := http.NewServeMux()
adminMux.HandleFunc("/admin/soundinbox/", soundinboxAdmin.Dashboard)
adminMux.HandleFunc("/admin/soundinbox/licenses", soundinboxAdmin.LicenseList)
adminMux.HandleFunc("/admin/soundinbox/licenses/generate", soundinboxAdmin.GenerateLicense)
adminMux.HandleFunc("/admin/soundinbox/licenses/", soundinboxAdmin.LicenseDetail)
adminMux.HandleFunc("/admin/soundinbox/orders", soundinboxAdmin.OrderList)
adminMux.HandleFunc("/admin/soundinbox/webhooks", soundinboxAdmin.WebhookLogs)
mux.Handle("/admin/soundinbox/", middleware.BasicAuth(cfg.SoundInbox.AdminUser, cfg.SoundInbox.AdminPass)(adminMux))
```

- [ ] **13.5** Add startup log lines:

```go
log.Printf("   SoundInbox API:  http://%s/api/soundinbox/health", cfg.Address())
log.Printf("   SoundInbox Admin: http://%s/admin/soundinbox/", cfg.Address())
```

- [ ] **13.6** Start the email retry sweep (every 10 minutes):

```go
go func() {
    ticker := time.NewTicker(10 * time.Minute)
    defer ticker.Stop()
    for range ticker.C {
        // Retry unsent license emails
        unsent, err := repo.GetUnsentEmails()
        if err != nil {
            log.Printf("[email-sweep] Error fetching unsent: %v", err)
            continue
        }
        for _, lic := range unsent {
            // Attempt resend (implementation in webhook handler)
            log.Printf("[email-sweep] Retrying email for license %s", lic.LicenseKey)
        }
    }
}()
```

### Test

```bash
cd /Users/txeo/Git/mac/go/drolosoft && go build ./cmd/server/ && echo "Build OK"
```

Then start the server and hit health:

```bash
cd /Users/txeo/Git/mac/go/drolosoft && go run ./cmd/server/ &
sleep 2
curl -s http://localhost:2005/api/soundinbox/health | jq .
kill %1
```

Expected health response:

```json
{
  "status": "ok",
  "database": "connected",
  "version": "1.0.0",
  "timestamp": "2026-04-21T..."
}
```

### Commit

```
feat(main): wire SoundInbox database, API, webhooks, pages, and admin

Initialize SQLite on startup, run migrations, create licensing repository.
Register all SoundInbox routes with appropriate middleware (rate limiting,
CORS, Basic Auth). Add email retry sweep and health check with DB status.
```

---

## Task 14: Manual E2E testing with curl

**No code changes — pure verification.**

### Steps

- [ ] **14.1** Start the server:

```bash
cd /Users/txeo/Git/mac/go/drolosoft
SOUNDINBOX_ADMIN_USER=admin SOUNDINBOX_ADMIN_PASS=testpass123 go run ./cmd/server/
```

- [ ] **14.2** Test health endpoint:

```bash
curl -s http://localhost:2005/api/soundinbox/health | jq .
```

Expected: `{"status":"ok","database":"connected",...}`

- [ ] **14.3** Test validate with nonexistent key:

```bash
curl -s -X POST http://localhost:2005/api/soundinbox/licenses/validate \
  -H "Content-Type: application/json" \
  -d '{"license_key":"ABCDE-FGHJK-MNPQR-STUVW-XY234"}' | jq .
```

Expected: `{"valid":false,"message":"License key not found","status":"not_found"}` (404)

- [ ] **14.4** Test validate with bad format:

```bash
curl -s -X POST http://localhost:2005/api/soundinbox/licenses/validate \
  -H "Content-Type: application/json" \
  -d '{"license_key":"bad"}' | jq .
```

Expected: `{"valid":false,"message":"Invalid license key format"}` (400)

- [ ] **14.5** Generate a license via admin:

```bash
curl -s -X POST http://localhost:2005/admin/soundinbox/licenses/generate \
  -u admin:testpass123 \
  -d "customer_email=test@example.com&customer_name=Test+User&reason=E2E+test" \
  -w "\n%{http_code}" -o /dev/null
```

Expected: 303 redirect (to license detail page). Extract the generated key from the redirect Location header.

- [ ] **14.6** Validate the generated license:

```bash
# Replace KEY with the actual generated key
curl -s -X POST http://localhost:2005/api/soundinbox/licenses/validate \
  -H "Content-Type: application/json" \
  -d '{"license_key":"<GENERATED-KEY>"}' | jq .
```

Expected: `{"valid":true,"status":"active","tier":"pro","features":{"max_accounts":5},...}`

- [ ] **14.7** Activate on a device:

```bash
curl -s -X POST http://localhost:2005/api/soundinbox/licenses/activate \
  -H "Content-Type: application/json" \
  -d '{
    "license_key":"<GENERATED-KEY>",
    "device_id":"TEST-DEVICE-001",
    "device_name":"Test MacBook",
    "device_model":"MacBookPro18,1",
    "os_version":"15.2",
    "app_version":"1.0.0"
  }' | jq .
```

Expected: `{"success":true,"message":"Device activated successfully",...}` (201)

- [ ] **14.8** Re-activate same device (idempotent):

```bash
# Same request again
curl -s -X POST http://localhost:2005/api/soundinbox/licenses/activate \
  -H "Content-Type: application/json" \
  -d '{
    "license_key":"<GENERATED-KEY>",
    "device_id":"TEST-DEVICE-001",
    "device_name":"Test MacBook",
    "device_model":"MacBookPro18,1",
    "os_version":"15.2",
    "app_version":"1.0.0"
  }' | jq .
```

Expected: `{"success":true,"message":"Device already activated",...}` (200)

- [ ] **14.9** Deactivate the device:

```bash
curl -s -X POST http://localhost:2005/api/soundinbox/licenses/deactivate \
  -H "Content-Type: application/json" \
  -d '{
    "license_key":"<GENERATED-KEY>",
    "device_id":"TEST-DEVICE-001"
  }' | jq .
```

Expected: `{"success":true,"message":"Device deactivated successfully","license":{...}}`

- [ ] **14.10** Verify admin dashboard loads:

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:2005/admin/soundinbox/ -u admin:testpass123
```

Expected: 200

- [ ] **14.11** Verify admin without auth is rejected:

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:2005/admin/soundinbox/
```

Expected: 401

- [ ] **14.12** Verify web pages load:

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:2005/soundinbox/privacy
curl -s -o /dev/null -w "%{http_code}" http://localhost:2005/soundinbox/pricing
curl -s -o /dev/null -w "%{http_code}" http://localhost:2005/soundinbox/download
curl -s -o /dev/null -w "%{http_code}" http://localhost:2005/soundinbox/changelog
```

Expected: All return 200.

- [ ] **14.13** Verify wrong HTTP method rejection:

```bash
curl -s -o /dev/null -w "%{http_code}" -X GET http://localhost:2005/api/soundinbox/licenses/validate
```

Expected: 405

### Commit

No commit — this is verification only. Document pass/fail results.

---

## Summary

| Task | Description | Est. Lines | Key Files |
|------|-------------|-----------|-----------|
| 1 | SQLite database package | ~200 | `internal/database/` |
| 2 | Configuration extension | ~100 | `internal/config/config.go` |
| 3 | License models | ~150 | `internal/licensing/models.go` |
| 4 | License keygen | ~200 | `internal/licensing/keygen.go` |
| 5 | License repository | ~500 | `internal/licensing/repository.go` |
| 6 | Webhook verification | ~200 | `internal/services/webhook/` |
| 7 | Email service | ~300 | `internal/services/email/` |
| 8 | API handlers | ~400 | `internal/handlers/soundinbox_api.go` |
| 9 | Webhook handler | ~250 | `internal/handlers/soundinbox_webhook.go` |
| 10 | Middleware | ~200 | `internal/middleware/` |
| 11 | Web pages + templates | ~500 | `internal/handlers/soundinbox_pages.go`, templates |
| 12 | Admin dashboard | ~600 | `internal/handlers/soundinbox_admin.go`, templates |
| 13 | Main.go wiring | ~100 | `cmd/server/main.go` |
| 14 | E2E curl testing | ~0 | Verification only |

**Total estimated: ~3,700 lines of Go code + ~2,000 lines of HTML templates**

**Critical path:** Tasks 1-5 must be sequential (each depends on the previous). Tasks 6-7 are independent of each other but depend on Task 5. Tasks 8-9 depend on Tasks 5-7. Task 10 is independent. Tasks 11-12 depend on the Drolosoft template system. Task 13 wires everything. Task 14 verifies.

**Parallelization opportunities:**
- Tasks 3 + 4 can run in parallel (models and keygen are independent)
- Tasks 6 + 7 can run in parallel (webhook verification and email are independent)
- Task 10 can run in parallel with Tasks 8-9
- Tasks 11 + 12 can run in parallel
