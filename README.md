# 📸🧹🗺️ immich-photo-manager

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Go Report Card](https://goreportcard.com/badge/github.com/drolosoft/immich-photo-manager)](https://goreportcard.com/report/github.com/drolosoft/immich-photo-manager)

> **📸🧹🗺️ MCP server for intelligent photo management with [Immich](https://immich.app) — your self-hosted library, understood.**

If you self-host [Immich](https://immich.app) and your library has grown past the point where you can manage it by hand, you know the feeling: thousands of photos with no GPS, duplicates scattered across Apple Photos and Google Takeout imports, screenshots mixed in with vacation shots, and albums that stopped being updated months ago. **immich-photo-manager** gives Claude direct access to your Immich instance through 16 MCP tools, plus 11 specialized skills that turn those tools into intelligent workflows — from finding cross-ecosystem duplicates with perceptual hashing to generating interactive travel maps from your GPS data.

This is a [Claude plugin](https://docs.claude.com) powered by an [MCP server](https://modelcontextprotocol.io). Install it, point it at your Immich instance, and talk to your photo library in plain English.

<p align="center"><img src="assets/demo.gif" alt="immich-photo-manager demo" width="800"></p>

---

## 📑 Table of Contents

- [✨ Why immich-photo-manager?](#-why-immich-photo-manager)
- [✨ Features](#-features)
- [🚀 Quick Start](#-quick-start)
- [📖 Commands](#-commands)
- [🧩 Skills](#-skills)
- [⚙️ How It Works](#️-how-it-works)
- [💡 Examples](#-examples)
- [📚 Documentation](#-documentation)
- [🚀 Deploy](#-deploy)
- [🔨 Building from Source](#-building-from-source)
- [📜 License & Philosophy](#-license--philosophy)

---

## ✨ Why immich-photo-manager?

Immich is excellent at storing, viewing, and searching your photos. But managing a large library — deduplication, metadata repair, album curation, storage analysis — still requires manual effort or custom scripts. immich-photo-manager bridges that gap by giving an AI assistant structured access to your library through the MCP protocol.

| | Manual / scripts | immich-photo-manager |
|:---:|---|---|
| 🔍 | Write API calls, parse JSON | **Natural language** — "find my sunset photos from Italy" |
| 🗺️ | Export GPS, cluster manually | **Geographic albums** — automatic GPS + CLIP + temporal matching |
| 🧹 | Hash files, diff checksums | **Perceptual hashing** — finds re-encoded duplicates across import sources |
| 📊 | Query database, build reports | **Library health** — one command for metadata quality, storage, recommendations |
| 📅 | SQL queries on timestamps | **Timeline gaps** — detects empty months and single-source coverage risks |
| 🔧 | EXIF tools, manual review | **Metadata fixer** — neighbor interpolation for missing GPS, broken timestamps |
| 🛡️ | Hope you don't delete the wrong thing | **Safety first** — never deletes without showing findings and asking |

---

## ✨ Features

| | Feature | What it does |
|:---:|---------|-------------|
| 🔍 | **AI-powered search** | Natural language photo search via CLIP ("sunset at the beach", "birthday cake") |
| 🗺️ | **Geographic albums** | Create albums organized by place — GPS + CLIP combined for smart curation |
| 🧹 | **Library cleanup** | Detect screenshots, duplicates, and low-quality images with multi-signal analysis |
| 🔎 | **Duplicate report** | Deep cross-source duplicate analysis using perceptual hashing — finds re-encoded copies across Apple Photos, Google Photos, and other imports |
| 🏥 | **Library health** | Comprehensive health check — asset inventory, metadata quality, storage breakdown, and recommendations |
| 📅 | **Timeline gaps** | Find missing months, sparse periods, and single-source coverage risks in your photo timeline |
| 🔧 | **Metadata fixer** | Detect and repair broken dates (noon/midnight), missing GPS, wrong timezones — with neighbor interpolation |
| 📌 | **Auto-album curator** | Finds new photos that belong in existing albums using GPS, CLIP, and temporal matching |
| 💾 | **Storage optimizer** | Identify RAW+JPEG pairs, oversized videos, and other space hogs with reclaimable space estimates |
| 👥 | **People report** | Face recognition insights — who appears most, unnamed clusters worth naming, co-occurrence patterns |
| 🌍 | **Travel map** | Interactive Leaflet.js map with clustered pins showing every place you've photographed |
| 🔗 | **Gallery publishing** | Create shared links to make albums publicly accessible |
| 📊 | **Library stats** | Photo counts, video counts, storage usage at a glance |
| 🛡️ | **Safety first** | Never deletes automatically — always shows findings and asks before acting |

---

## 🚀 Quick Start

### Prerequisites

- A running [Immich](https://immich.app) instance (self-hosted, v1.90+)
- An Immich API key ([how to create one](https://immich.app/docs/features/command-line-interface#obtain-the-api-key))
- Go 1.24+ (to build the MCP server)
- Claude Desktop with [Cowork mode](https://docs.claude.com), or [Claude Code](https://docs.claude.com/en/docs/claude-code) CLI

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

That's it. Open Claude and say "how healthy is my photo library?" to get started.

### Additional dependencies (optional)

Some advanced skills require Python packages or direct database access:

```bash
pip3 install Pillow imagehash pillow-heif
```

| Package | Used by | Purpose |
|---------|---------|---------|
| `Pillow` | duplicate-report | Image loading |
| `imagehash` | duplicate-report | Perceptual hashing (pHash) |
| `pillow-heif` | duplicate-report | HEIC/HEIF support (Apple Photos) |
| PostgreSQL client | library-health, timeline-gaps, people-report, storage-optimizer | Database-level analysis |

---

## 📖 Commands

Slash commands for common workflows — type them directly in Claude:

| Command | Description |
|---------|-------------|
| `/immich-status` | 📊 Check connection and library statistics |
| `/create-album` | 🗺️ Create a geographic album from a location |
| `/cleanup` | 🧹 Scan for screenshots, duplicates, and junk |
| `/my-travels` | 🌍 Discover all travel destinations in your library |

---

## 🧩 Skills

Skills are specialized workflows that combine MCP tools with domain knowledge. Each skill handles a specific photo management task end-to-end.

### 🗺️ Album Manager

Create and curate albums organized by geography. Say "create an album from my Italy trip" and it searches by GPS + AI visual search, filters out junk, and builds a curated album with 20–50 photos.

### 🔍 Photo Search

Natural language search across your entire library. "Find my sunset photos", "photos from 2019 in Barcelona", "pictures of Maria". Translates intent into optimal search queries combining GPS, CLIP, and metadata filters.

### 🧹 Photo Cleanup

Detect screenshots (by screen resolution + missing GPS + no lens info), duplicates (exact hash + format duplicates + near-duplicates), and low-quality images. Reports findings with confidence levels and waits for your approval.

### 🔎 Duplicate Report

Deep duplicate analysis using perceptual hashing (pHash). Designed for libraries with photos imported from multiple ecosystems (Apple Photos, Google Takeout, manual folder copies) where the same photo gets re-encoded by each platform — making checksums and filenames useless for matching.

### 🏥 Library Health Report

Comprehensive health assessment: asset inventory, import source breakdown, metadata completeness (GPS coverage, EXIF dates, camera info), file format distribution, and actionable recommendations. The "annual checkup" for your photo library.

### 📅 Timeline Gaps

Analyzes your photo timeline month by month to detect empty months, sparse periods, and single-source coverage risks. Answers questions like "if I delete Google Photos, which months would I lose?" and "are there months where I'm missing photos?"

### 🔧 Metadata Fixer

Scans for broken or suspicious metadata — noon/midnight timestamps (from path-recovered dates), missing GPS on geotagged trips, wrong timezones. Proposes corrections using folder structure, neighboring photos, and EXIF inference. All fixes require approval.

### 📌 Auto-Album Curator

Monitors your library for new photos that match existing albums. Uses GPS proximity, CLIP visual similarity, and temporal patterns to suggest additions. Keeps your albums fresh without manual curation.

### 💾 Storage Optimizer

Identifies the biggest storage consumers: RAW+JPEG pairs, oversized videos, large screenshots, format inefficiencies. Shows reclaimable space estimates, growth projections, and "months until disk full" calculations.

### 👥 People Report

Analyzes Immich's face recognition data: who appears most, unnamed clusters worth naming, co-occurrence patterns (people appearing together), timeline per person. Helps clean up the unnamed faces backlog.

### 🌍 Travel Map

Generates an interactive HTML map (Leaflet.js + MarkerCluster) with clustered pins showing every location where photos were taken. Includes photo counts, date ranges, and heatmap overlay. Outputs a standalone HTML file.

---

## ⚙️ How It Works

### Architecture

```
Claude ←→ MCP (Streamable HTTP) ←→ Go Server ←→ Immich REST API
                                     :8626          your-instance
```

The MCP server is a single Go binary built with [mcp-go](https://github.com/mark3labs/mcp-go) v0.32.0. It exposes 16 tools over Streamable HTTP transport on `/mcp`, with a health check on `/health`. All credentials are passed via environment variables — nothing is hardcoded.

### 16 MCP Tools

| Category | Tools |
|----------|-------|
| 🏥 Health | `ping`, `get_server_version`, `get_statistics` |
| 📷 Assets | `get_asset_info`, `get_map_markers` |
| 🔍 Search | `search_metadata`, `search_smart` (CLIP) |
| 📁 Albums | `list_albums`, `get_album`, `create_album`, `update_album`, `delete_album`, `add_assets_to_album`, `remove_assets_from_album` |
| 🔗 Sharing | `list_shared_links`, `create_shared_link`, `delete_shared_link` |

Skills orchestrate these tools into multi-step workflows. For example, the Album Manager skill calls `get_map_markers` to find GPS clusters, `search_smart` to refine by visual similarity, `create_album` to build the album, and `add_assets_to_album` to populate it — all from a single natural language request.

---

## 💡 Examples

### Create geographic albums from your travels

```
"Create albums for all the places I've traveled"
→ Scans GPS data, clusters by location, identifies destinations
→ Proposes album list for approval
→ Creates albums with curated selections (20-50 photos each)
```

### Run a library health check

```
"How healthy is my library?"
→ 44,579 assets (39,596 photos + 4,983 videos), 182 GB
→ GPS coverage: 72.3%, EXIF dates: 89.1%
→ 1,204 suspicious timestamps (noon/midnight)
→ Recommends: metadata-fixer, timeline-gaps analysis
```

### Find and remove cross-ecosystem duplicates

```
"Run a duplicate report"
→ Discovers import sources (Apple Photos, Google Photos)
→ Scans 39,500 files with perceptual hashing (~15 min)
→ Reports: 795 cross-source duplicates (4% overlap), 117 internal
→ "Want me to remove the 912 duplicates?"
```

### Generate an interactive travel map

```
"Show me everywhere I've been"
→ Extracts GPS from 28,616 geotagged photos
→ Clusters into 47 locations across 14 countries
→ Generates interactive HTML map with Leaflet.js
→ Opens in browser with clustered pins, heatmap, and timeline
```

### Find gaps in your photo timeline

```
"Are there months I'm missing photos?"
→ Coverage: Jan 2014 — Mar 2026 (147 months)
→ 3 empty months: Aug 2015, Feb 2016, Nov 2019
→ 7 sparse months (< 10% of average)
→ Google Photos ends Dec 2023 — intentional?
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

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[Getting Started](doc/GETTING-STARTED.md)** | Step-by-step installation, configuration, first run, deployment options, and troubleshooting |
| **[Skills Reference](doc/SKILLS.md)** | Comprehensive reference for all 11 skills — workflows, triggers, parameters, output formats |
| **[MCP Tools Reference](doc/MCP-TOOLS.md)** | All 16 MCP tools — parameters, return types, examples, architecture |

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

See `deploy/nginx-immich-mcp.conf.example` for a reverse proxy template with rate limiting.

---

## 🔨 Building from Source

**Prerequisites**: Go 1.24+

```sh
git clone https://github.com/drolosoft/immich-photo-manager.git
cd immich-photo-manager
go build -o immich-mcp-server .
```

The binary is pure Go with minimal dependencies (`mcp-go` for the MCP transport, `godotenv` for `.env` loading). No CGO, no Docker required — build it and run it.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `IMMICH_BASE_URL` | `http://localhost:2283` | Immich server base URL |
| `IMMICH_API_KEY` | *(required)* | Immich API key |
| `MCP_PORT` | `8626` | MCP server port |

Copy `.env.example` to `.env` and fill in your values, or export them directly.

---

## 📜 License & Philosophy

**MIT License** — free to use, modify, and distribute.

This project was born from a real library: 44,000 photos across Apple Photos, Google Takeout, and manual imports, accumulated over 12 years on a self-hosted Immich instance. Duplicates hiding behind different encodings. 30% of photos missing GPS. Timestamps corrupted by date-recovery tools. Albums that hadn't been updated in months.

There was no single tool that could understand the full picture. So we built one — an MCP server that lets an AI assistant see your library the way you do, and help you fix what's broken.

**Geography first, chronology second.** Photos are organized by place, not date. If you visited Mexico twice, you get one "Mexico" album, not "Mexico 2018" and "Mexico 2023".

**Err on the side of more.** When creating albums automatically, the plugin creates more albums than you might want rather than fewer. It's easier to merge or delete an unwanted album than to discover a missing one.

**Never delete without asking.** All destructive operations require explicit confirmation. Cleanup scans report findings and wait for your decision. Bulk operations default to dry-run mode.

This is **shared, not staffed**. It works, it's tested, and it solves the problem it was built for. If you find a bug, PRs are welcome. If you want a feature, fork it — that's what open source is for.

**Forged by [Drolosoft](https://drolosoft.com)** · *Tools we wish existed*
