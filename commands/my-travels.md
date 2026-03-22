---
description: Discover all travel destinations in your photo library
allowed-tools: ["mcp__immich__*"]
---

Analyze the Immich library to discover all geographic locations where photos were taken.

1. Search for all assets that have GPS data
2. Cluster by location (group photos within 30km of each other)
3. Identify the city/region/country for each cluster
4. Count photos per cluster
5. Sort by photo count (most photos first)

Present as a travel map:

```
🗺️ Your Travel Destinations
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Found photos from {count} distinct locations across {countries} countries.

🇮🇹 Italy
   📍 Roma — {count} photos ({date_range})
   📍 Cinque Terre — {count} photos ({date_range})
   📍 Venezia — {count} photos ({date_range})

🇪🇬 Egypt
   📍 Cairo & Luxor — {count} photos ({date_range})

🇲🇽 Mexico
   📍 Oaxaca — {count} photos ({date_range})

[... more destinations ...]

📊 {no_gps_count} photos have no GPS data ({percentage}%)

Want me to create albums for these destinations?
```

After presenting, offer to create geographic albums using the album-manager skill.
