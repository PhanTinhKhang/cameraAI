# 🚨 Alert System Scenario Analysis

## Setup

| Entity | Location | Details |
|--------|----------|---------|
| **User (ptk)** | `16.0379, 108.2387` | Radius configurable (tested at 1.5km and 5km) |
| **cam01** (Đà Nẵng Mỹ An) | `16.0382, 108.2392` | Road distance to user: **0.107 km** |
| **cam02** (Hoàng Hoa Thám) | `16.0592, 108.2372` | Road distance to user: **3.013 km** |

### Range Check by Radius

| Camera | Road Distance | 1.5km Radius | 5km Radius |
|--------|--------------|:------------:|:----------:|
| cam01 | 0.107 km | ✅ IN RANGE | ✅ IN RANGE |
| cam02 | 3.013 km | ❌ OUT | ✅ IN RANGE |

> [!IMPORTANT]
> With **5km radius**, both cameras are in range. The user will receive alerts from **both** cameras. With **1.5km**, only cam01 triggers alerts.

---

## Notification Channels

| Channel | When | How |
|---------|------|-----|
| **WebSocket** | App **open** | `broadcast()` → Flutter checks OSRM distance locally → popup + siren if in range, red marker if not |
| **FCM Push** | App **closed/killed** | Backend checks distance server-side → data-only FCM with `priority=high` → background handler shows notification |

---

## Scenarios with 1.5km Radius

### Scenario 1: cam01 triggers (0.107km — IN RANGE)
- ✅ Push notification sent
- ✅ Popup + siren + local notification
- 🔴 Red marker + 1500m circle on map

### Scenario 2: cam02 triggers (3.013km — OUT OF RANGE)
- ❌ No push notification
- ❌ No popup/siren
- 🔴 Red marker on map only (user can tap to view)

### Scenario 3: cam02 first, then cam01 30s later
| Time | Camera | Distance | Result |
|------|--------|----------|--------|
| T+0s | cam02 | 3.013km > 1.5km | 🔴 Red marker only |
| T+30s | cam01 | 0.107km ≤ 1.5km | ✅ Full alert (push + popup + siren) |

### Scenario 4: Both simultaneously
- cam01: ✅ Full alert
- cam02: ❌ Red marker only

### Scenario 5: App closed
- cam01: ✅ FCM push notification
- cam02: ❌ Nothing

---

## Scenarios with 5km Radius

> [!WARNING]
> With 5km radius, **BOTH cameras** are within range (cam01=0.107km, cam02=3.013km). Every alert from either camera will trigger full notifications.

### Scenario A: cam01 triggers (0.107km — IN RANGE)
- ✅ Push + popup + siren

### Scenario B: cam02 triggers (3.013km — IN RANGE)
- ✅ Push + popup + siren (this was previously silent with 1.5km!)

### Scenario C: Both simultaneously
- ✅ **TWO** push notifications sent
- ✅ **TWO** popup alerts shown sequentially
- 🔊 Siren plays **twice**
- 🗺️ Map shows **two** red markers with **5000m** circles (overlapping!)

### Scenario D: cam02 first, cam01 30s later
| Time | Camera | Distance | Result |
|------|--------|----------|--------|
| T+0s | cam02 | 3.013km ≤ 5.0km | ✅ Full alert |
| T+30s | cam01 | 0.107km ≤ 5.0km | ✅ Full alert |
Both events trigger full notifications.

### Scenario E: App closed
- cam01: ✅ FCM push
- cam02: ✅ FCM push (now within range!)

---

## Known Issues — All Fixed ✅

### 1. ~~Duplicate User Records~~ → FIXED
Cleaned up 3 duplicate/invalid records from MongoDB. Reduced from 11 → 8 users. Invalid `dummy_token` entries deleted. Duplicate FCM tokens consolidated to keep only the newest record.

### 2. ~~OSRM Reliability~~ → FIXED
Added an in-memory cache (60s TTL, ~11m precision) for OSRM distance results. This:
- Reduces API calls from N-per-alert to ~unique-locations-per-alert
- Prevents rate limiting from the public OSRM API
- Falls back to haversine with a visible warning log if OSRM is unavailable

### 3. ~~Battery Optimization~~ → ALREADY HANDLED
- `AndroidManifest.xml` declares `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`
- Flutter app requests `ignoreBatteryOptimizations` permission on startup
- FCM messages use `AndroidConfig(priority="high")` for immediate delivery
- Data-only payloads avoid OEM notification filters

### 4. ~~Hardcoded Circle Radius~~ → FIXED
The red alert circle on the Flutter map now uses `ApiService.preferredRadius` (user's setting) instead of a hardcoded 2000m. Circle radius matches what the user configured in Settings.
