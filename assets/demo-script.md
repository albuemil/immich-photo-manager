# Demo Script — immich-photo-manager

> Reproducible sequence for generating the demo GIF.
> The "tape file" equivalent for GUI-based plugin demos.

## Version
- **Script version**: 1.0.0
- **Last recorded**: (not yet recorded)
- **Output**: `assets/demo.gif`

## Method

### Option 1 — Automated HTML Player (Primary)
Serve `assets/demo.html` locally and record with Kap or gif_creator.

```bash
cd ~/Git/drolosoft/immich-photo-manager/assets
python3 -m http.server 9876
# Open http://localhost:9876/demo.html
# Record with Kap → export as GIF
```

### Option 2 — Manual with Kap (Hybrid)
See Vikunja task #214 for full runbook.

---

## Scene Sequence

### Scene 1 — Search
| Field | Value |
|-------|-------|
| **Prompt** | Find my photos from Mexico |
| **Tool** | `search_metadata` |
| **Result** | 10 photos, September 2021 |
| **Duration** | ~3s |

### Scene 2 — Album Creation
| Field | Value |
|-------|-------|
| **Prompt** | Create an album called "Mexico 2021" with those photos |
| **Tools** | `create_album` → `add_assets_to_album` |
| **Result** | Album created with 10 photos |
| **Duration** | ~3s |
| **Cleanup** | Delete test album after recording |

### Scene 3 — Library Cleanup
| Field | Value |
|-------|-------|
| **Prompt** | Scan my library for screenshots and duplicates |
| **Tools** | `search_metadata` → `search_smart` |
| **Result** | 1,247 screenshots · 389 duplicates · 3.2 GB reclaimable |
| **Duration** | ~4s |

---

## Shared Link for Thumbnails
- **Key**: `PLa3weHKVQrv89IgUdTVPjaco0s2yLcWGuXkQ331zXlxkRJiiNhErLGGPYsudTxr5_w`
- **Album**: `_demo-gif-temp` (7 landscape photos, no faces)
- **URL**: `http://localhost:3001/api/assets/{id}/thumbnail?key={KEY}`

## Safety
- ONLY search by location — never by faces
- ONLY show landscape/travel photos
- Delete test albums after recording

## Post-Recording
1. Verify GIF < 5 MB
2. Save to `assets/demo.gif`
3. Update README img tag
4. Commit + push both remotes
5. Delete `_demo-gif-temp` album and shared link
