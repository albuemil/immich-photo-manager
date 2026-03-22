# Geographic Search Patterns

Reference data for searching photos by location. Use GPS bounding boxes for precise results, CLIP queries as fallback.

## Search Strategy by Location Type

### Countries with multiple visits
Search each known city/region separately, then merge results. Example for Mexico:
- Search: Chiapas area (lat 16.75, lon -93.12, radius 100km)
- Search: Oaxaca area (lat 17.07, lon -96.72, radius 50km)
- Search: Mexico City area (lat 19.43, lon -99.13, radius 30km)
- Merge unique results → one "México" album or separate city albums

### City visits
Use tight radius (5-15km) centered on city center. Expand if few results.

### Island/regional visits
Use moderate radius (20-50km) to capture the full area.

### Road trips / multi-stop
Search each stop separately, then combine into a thematic album.

## Common GPS Centers (expand as needed)

| Location | Latitude | Longitude | Suggested Radius |
|----------|----------|-----------|-----------------|
| Roma, Italia | 41.9028 | 12.4964 | 15km |
| Cinque Terre, Italia | 44.1461 | 9.6563 | 10km |
| Venezia, Italia | 45.4408 | 12.3155 | 10km |
| Trieste, Italia | 45.6495 | 13.7768 | 10km |
| Como, Italia | 45.8080 | 9.0852 | 15km |
| Cairo, Egypt | 30.0444 | 31.2357 | 30km |
| Luxor, Egypt | 25.6872 | 32.6396 | 20km |
| Ciudad de México | 19.4326 | -99.1332 | 30km |
| Oaxaca, México | 17.0732 | -96.7266 | 50km |
| Tuxtla Gutiérrez, México | 16.7528 | -93.1152 | 100km |
| Guatemala / Flores | 16.9304 | -89.8923 | 50km |
| Berlín, Germany | 52.5200 | 13.4050 | 20km |
| Londres, UK | 51.5074 | -0.1278 | 20km |
| Edimburgo, UK | 55.9533 | -3.1883 | 15km |
| Ámsterdam, Netherlands | 52.3676 | 4.9041 | 15km |
| Varsovia, Poland | 52.2297 | 21.0122 | 15km |
| Bogotá, Colombia | 4.7110 | -74.0721 | 20km |
| Santo Domingo, Dom. Rep. | 18.4861 | -69.9312 | 30km |
| Mauritius | -20.3484 | 57.5522 | 40km |
| Kärnten, Austria | 46.7222 | 13.8553 | 40km |
| Istria, Croatia | 45.1300 | 13.9000 | 40km |
| Barcelona, España | 41.3874 | 2.1686 | 15km |
| Lanzarote, España | 29.0469 | -13.5899 | 25km |
| La Palma, España | 28.6835 | -17.7642 | 20km |
| Plasencia, España | 40.0304 | -6.0907 | 15km |
| Sevilla, España | 37.3891 | -5.9845 | 15km |
| Madrid, España | 40.4168 | -3.7038 | 20km |
| Begur, España | 41.9553 | 3.2073 | 10km |
| La Vera, España | 40.1167 | -5.4500 | 20km |
| Mérida, España | 38.9160 | -6.3440 | 10km |
| Fuerteventura, España | 28.3587 | -14.0537 | 30km |

## CLIP Search Queries by Destination

When GPS is unavailable, use these semantic queries:

| Destination | CLIP Queries |
|-------------|-------------|
| Lanzarote | "volcanic landscape", "black sand beach", "white village Canary Islands" |
| Cinque Terre | "colorful houses cliff ocean Italy", "Riomaggiore", "Italian riviera" |
| Egypt | "pyramid", "sphinx", "Nile river", "Luxor temple", "hieroglyphics" |
| Mexico (Chiapas) | "jungle waterfall Mexico", "Mayan ruins", "canyon Chiapas" |
| La Palma | "banana plantation Canary Islands", "observatory mountain", "laurel forest" |

## Album Splitting Guidelines

When to create sub-albums vs one album:
- **One album**: Short trip (1-7 days), single city/island, < 80 photos
- **Multiple albums**: Multi-city trip, > 80 photos per location, distinctly different areas
- **Example**: "Italia" could be one album OR separate "Roma", "Cinque Terre", "Venezia" — depends on photo count per location
