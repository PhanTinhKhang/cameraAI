# Bug Fixes & Feature Improvements for Mobile App + Dashboard

## Summary of Issues & Fixes

There are 6 issues reported. Here is my root-cause analysis and proposed fix for each:

---

## Bug 1: Google Maps not showing anything on the app

**Root Cause**: The API key `AQ.Ab8RN6IemWQhlcTY7FT5BLET_i_mUkzQIWgkn0ZmiLVlfrKdyw` is **not a valid Google Maps API key**. Google Maps Platform API keys start with `AIzaSy...`. The key you provided appears to be a different type of credential (possibly a service account key or another Google service token).
I updated api key in json but havent sync this key yet

> [!CAUTION]
> The map will remain blank until a valid Google Maps API key is provided. You need to go to [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials), create a new **API Key**, and enable the **Maps SDK for Android** and **Directions API** for it.

**Fix**: Once you have a valid key (starts with `AIzaSy...`), update `api_keys.json` and re-run `python sync_keys.py`. I will also add validation in the sync script to warn if the key format looks wrong.

---

## Bug 2: No sound on notification

**Root Cause**: The `AndroidNotificationDetails` in [main.dart](file:///d:/cameraAI2/flutter_app/lib/main.dart#L22-L31) doesn't specify a notification sound. For a Grab-like urgent notification, we need to set `playSound: true` and use a custom notification channel with max importance.

**Fix**:
- Update `AndroidNotificationDetails` to include `playSound: true`, `sound: RawResourceAndroidNotificationSound('notification')` (or default), and `enableVibration: true`.
- Also set `channelShowBadge: true` for consistency.

---

## Bug 3: Translate all to Vietnamese and rebuild gamification

**Root Cause**: Most of the app is already in Vietnamese, but there are scattered English strings and the gamification badge names could be more engaging.

**Fix**: Audit all screens and replace any remaining English strings. Redesign gamification with more Vietnamese-friendly badges and more granular levels:

| Points | Badge | Icon |
|--------|-------|------|
| 0-49 | Người tốt bụng | 🌱 |
| 50-149 | Tân hiệp sĩ | 💚 |
| 150-349 | Hiệp Sĩ Tập Sự | 🛡️ |
| 350-699 | Hiệp Sĩ Đường Phố | ⚔️ |
| 700-1199 | Anh Hùng Cứu Nạn | 🦸 |
| 1200+ | Huyền Thoại nhân ái | 🏆 |

---

## Bug 4: Alert popup from bottom when app is open

**Root Cause**: Currently when a WebSocket alert arrives, the app only shows a small red banner at the top of the map. The user wants a rich bottom sheet popup showing: location, distance, accident type, and video playback.

**Fix**: Replace the top banner approach with a `showModalBottomSheet` that slides up from the bottom containing:
- Alert type icon + Vietnamese label
- Location name
- Distance from user (in meters)
- Embedded video player for playback
- "Tôi tham gia cứu hộ" (Accept) button

---

## Bug 5: Push notification with sound when app is closed

**Root Cause**: The Firebase push notification already works, but doesn't play a custom sound. When the user taps the notification, it opens the app but doesn't navigate to the alert.

**Fix**:
- Add `sound` configuration to `AndroidNotificationDetails` in the background handler.
- Handle `onMessageOpenedApp` and `getInitialMessage` to extract `alert_id` from the notification data, fetch the alert details, and navigate directly to the mission/alert screen.

---

## Bug 6: App and Dashboard crash when pressing buttons that communicate with admin

**Root Cause**: The `volunteer_status_changed` action from the WebSocket is **not handled** in [useAlerts.js](file:///d:/cameraAI2/ai-cam-web/src/hooks/useAlerts.js#L40-L65). When the app sends a status update (e.g. "false_alarm" or "completed"), the backend broadcasts `{"action": "volunteer_status_changed", ...}`. The dashboard's `ws.onmessage` tries to add it as a new alert (the `else` branch at line 59), which corrupts the alerts state because it's not a full alert object — it's just a status change message. This causes the React dashboard to crash when it tries to render the corrupted data.

On the **Flutter side**, the crash likely happens because:
1. The `_id` field from `widget.alert['_id']` might be `null` if the alert was constructed from a push notification without proper data.
2. The WebSocket reconnection after a status update might cause a state conflict.

**Fix**:
- **Dashboard ([useAlerts.js](file:///d:/cameraAI2/ai-cam-web/src/hooks/useAlerts.js))**: Add explicit handling for `volunteer_status_changed` action in the WebSocket message handler — update the volunteer's status within the matching alert instead of adding a new entry.
- **Flutter ([mission_screen.dart](file:///d:/cameraAI2/flutter_app/lib/screens/mission_screen.dart))**: Add `try/catch` around the API calls and handle the case where `alert['_id']` is null. Also add null-safety for `widget.alert['location']`.

---

## Proposed Changes

### Phase 3: Final Polishing & Fixes

#### 1. WebRTC Connection Fix
**Root Cause**: WebRTC server runs on port `8080` (arlert.py), but the app connects via ngrok to port `8000` (alert_server.py).
**Fix**: Add an `/offer` proxy endpoint in `Arlert_BE/alert_server.py` that forwards the WebRTC SDP request to `localhost:8080/offer`. Update `flutter_app` to point to `/offer` via the normal API URL.

#### 2. Dashboard Volunteer Duplication
**Root Cause**: React state in `useAlerts.js` appends `volunteer_added` blindly, causing duplicates if history and WebSocket race.
**Fix**: In `ai-cam-web/src/hooks/useAlerts.js`, check if `v.user_id === msg.volunteer.user_id` exists before appending.

#### 3. Dashboard UI: Volunteer Status & Rescue Sent
**Fix**: 
- In `ai-cam-web/src/App.jsx`, update the main alert list (not just focus view) to show a summary of volunteer statuses (e.g., "1 Đang đến, 1 Hoàn thành").
- Display `rescue_sent` status clearly on the dashboard.

#### 4. App UI: Volunteer List & Rescue Status in Mission Screen
**Fix**: 
- In `flutter_app/lib/screens/mission_screen.dart`, add a periodic timer to fetch the latest alert data.
- Display the list of co-volunteers and their statuses.
- Show a prominent indicator if Admin has dispatched rescue (`rescue_sent` == true).

#### 5. App UI: Auto-update Points & Sign Out
**Fix**:
- In `flutter_app/lib/screens/status_screen.dart`, implement a `Timer.periodic` to fetch points automatically.
- Add a "Đăng xuất" (Sign Out) button at the bottom of the status screen that clears `SharedPreferences` and restarts the app.

#### 6. Improve Congratulation Message
**Fix**:
- Update `alert_server.py` push notification message to be more engaging and motivating (e.g., "Huy chương danh dự! 🌟 Hành động nghĩa hiệp của bạn vừa cứu được nhiều người. Tặng bạn 25 điểm cống hiến!").

#### 7. Volunteer Export File (Phone Number ID)
**Fix**:
- In `alert_server.py`, whenever a user registers or updates, write/append their details to a local `volunteers_list.json` file, using their phone number as the primary key.

## Verification Plan
### Automated Tests
- Restart backend to apply proxy changes.
- Ensure React compiles successfully.
### Manual Verification
- Test WebRTC connection on app.
- Ensure volunteer list only shows unique users.
- Verify Mission screen auto-updates co-volunteers.
- Check that `volunteers_list.json` is generated.
- Translate any remaining English strings.
- Add badge icons and a more visual design.

#### [MODIFY] [api_service.dart](file:///d:/cameraAI2/flutter_app/lib/services/api_service.dart)
- Translate remaining English debug strings.

#### [MODIFY] [sync_keys.py](file:///d:/cameraAI2/sync_keys.py)
- Add validation to warn if the API key doesn't look like a Google Maps key.

---

## Open Questions

> [!IMPORTANT]
> **Google Maps API Key**: Your current key `AQ.Ab8...` does not appear to be a valid Google Maps Platform key (those start with `AIzaSy...`). Could you double-check and provide the correct key? Without it, the map will remain blank.

---

## Verification Plan

### Build & Test
- Run `flutter analyze` to confirm zero errors.
- Run `flutter build apk` to produce the final APK.
- Test the dashboard by starting the dev server and sending a test alert.

### Manual Verification
- Install APK and verify Google Maps renders (once valid key is provided).
- Trigger an alert and verify the bottom sheet popup appears with sound.
- Kill the app and trigger an alert to verify push notification with sound.
- Tap the notification to verify it opens the alert screen.
- Press "Báo Cáo Báo Động Giả" and "Hoàn Thành Nhiệm Vụ" to verify no crash.
- Check dashboard doesn't crash when volunteer status updates arrive.
