# 📸 Immich Photo Manager

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **MCP server for intelligent photo management with [Immich](https://immich.app) — search, curate geographic albums, clean up libraries, and publish galleries.**

---

## 📑 Table of Contents

- [Features](#-features)
- [Quick Start](#-quick-start)
- [Commands](#-commands)
- [Skills](#-skills)
- [How It Works](#-how-it-works)
- [Examples](#-examples)
- [Deploy](#-deploy)
- [Philosophy](#-philosophy)
- [License](#-license)

---

## ✨ Features

| | Feature | What it does |
|:---:|---------|-------------|
| 🔍 | **AI-powered search** | Natural language photo search via CLIP ("sunset at the beach", "birthday cake") |
| 🗺️ | **Geographic albums** | Create albums organized by place — GPS + CLIP combined for smart curation |
| 🧹 | **Library cleanup** | Detect screenshots, duplicates, and low-quality images with multi-signal analysis |
| 🔗 | **Gallery publishing** | Create shared links to make albums publicly accessible |
| 📊 | **Library stats** | Photo counts, video counts, storage usage at a glance |
| 🛡️ | **Safety first** | Never deletes automatically — always shows findings and asks before acting |

---

## 🚀 Quick Start

### Prerequisites

- A running [Immich](https://immich.app) instance (self-hosted)
- An Immich API key ([how to create one](https://immich.app/docs/features/command-line-interface#obtain-the-api-key))
- Go 1.24+ (to build the MCP server)

### Build & Run

```sh
git clone https://github.com/drolosoft/immich-photo-manager.git
cd immich-photo-manager
go build -o immich-mcp-server .
```

```sh
export IMMICH_BASE_URL="http://your-immich-server:2283"
export IMMICH_API_KEY="your-api-key-here"
./immich-mcp-server
```

The server starts on port `8626` by default (override with `MCP_PORT` env var).

### Configure Claude

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "immich": {
      "url": "http://localhost:8626/mcp"
    }
  }
}
```

---

## 📖 Commands

| Command | Description |
|---------|-------------|
| `/immich-status` | 📊 Check connection and library statistics |
| `/create-album` | 🗺️ Create a geographic album from a location |
| `/cleanup` | 🧹 Scan for screenshots, duplicates, and junk |
| `/my-travels` | 🌍 Discover all travel destinations in your library |

---

## 🧩 Skills

### 🗺️ Album Manager

Create and curate albums organized by geography. Say "create an album from my Italy trip" and it searches by GPS + AI visual search, filters out junk, and builds a curated album with 20-50 photos.

### 🔍 Photo Search

Natural language search across your entire library. "Find my sunset photos", "photos from 2019 in Barcelona", "pictures of Maria". Translates intent into optimal search queries combining GPS, CLIP, and metadata filters.

### 🧹 Photo Cleanup

Detect screenshots (by screen resolution + missing GPS + no lens info), duplicates (exact hash + format duplicates + near-duplicates), and low-quality images. Reports findings with confidence levels and waits for your approval.

---

## ⚙️ How It Works

### 16 MCP Tools

| Category | Tools |
|----------|-------|
| 🏥 Health | `ping`, `get_server_version`, `get_statistics` |
| 📷 Assets | `get_asset_info`, `get_map_markers` |
| 🔍 Search | `search_metadata`, `search_smart` (CLIP) |
| 📁 Albums | `list_albums`, `get_album`, `create_album`, `update_album`, `delete_album`, `add_assets_to_album`, `remove_assets_from_album` |
| 🔗 Sharing | `list_shared_links`, `create_shared_link`, `delete_shared_link` |

### Architecture

```
Claude ←→ MCP (Streamable HTTP) ←→ Go Server ←→ Immich REST API
                                     :8626          your-instance
```

- **Go MCP server** using [mcp-go](https://github.com/mark3labs/mcp-go) v0.32.0
- Streamable HTTP transport on `/mcp`, health check on `/health`
- Forces `tcp4` binding for IPv4 network compatibility
- All credentials via environment variables (never hardcoded)

---

## 💡 Examples

### Create geographic albums from your travels

```
"Create albums for all the places I've traveled"
→ Scans GPS data, clusters by location, identifies destinations
→ Proposes album list for approval
→ Creates albums with curated selections (20-50 photos each)
```

### Clean up your library

```
"How many screenshots are in my library?"
→ Scans library using resolution + EXIF analysis
→ Reports findings by confidence level
→ "Want me to archive them?"
```

### Search naturally

```
"Find photos of sunsets I took in Italy"
→ Combines GPS (Italy bounding box) + CLIP ("sunset")
→ Returns matching photos across Roma, Cinque Terre, Venezia
```

---

## 🚀 Deploy

### macOS launchd

A template plist is included at `deploy/com.immich-mcp.plist.example`. Copy and configure:

```sh
cp deploy/com.immich-mcp.plist.example ~/Library/LaunchAgents/com.immich-mcp.plist
# Edit the plist to set your IMMICH_BASE_URL, IMMICH_API_KEY, and binary path
launchctl load ~/Library/LaunchAgents/com.immich-mcp.plist
```

### Nginx reverse proxy

See `deploy/nginx-immich-mcp.conf.example` for a reverse proxy template.

---

## 🧭 Philosophy

**Geography first, chronology second.** Photos are organized by place, not date. If you visited Mexico twice, you get one "Mexico" album (or sub-albums by city), not "Mexico 2018" and "Mexico 2023".

**Err on the side of more.** When creating albums automatically, the plugin creates more albums than you might want rather than fewer. It's easier to merge or delete an unwanted album than to discover a missing one.

**Never delete without asking.** All destructive operations require explicit confirmation. Cleanup scans report findings and wait for your decision. Bulk operations default to dry-run mode.

---

## 📜 License

**MIT License** — free to use, modify, and distribute.

**Forged by [Drolosoft](https://drolosoft.com)** · *Tools we wish existed*
