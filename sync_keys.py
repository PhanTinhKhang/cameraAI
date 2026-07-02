import json
import os
import re

# Load keys
keys_file = 'api_keys.json'
if not os.path.exists(keys_file):
    print(f"Error: {keys_file} not found.")
    exit(1)

with open(keys_file, 'r', encoding='utf-8') as f:
    keys = json.load(f)

maps_key = keys.get('GOOGLE_MAPS_API_KEY', '')

print(f"Syncing Google Maps API Key...")

# 1. Update AndroidManifest.xml
manifest_path = os.path.join('flutter_app', 'android', 'app', 'src', 'main', 'AndroidManifest.xml')
if os.path.exists(manifest_path):
    with open(manifest_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Replace the android:value string for com.google.android.geo.API_KEY
    content = re.sub(
        r'<meta-data android:name="com\.google\.android\.geo\.API_KEY"[\s\n]*android:value=".*?"/>',
        f'<meta-data android:name="com.google.android.geo.API_KEY"\n            android:value="{maps_key}"/>',
        content
    )
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(" - Updated AndroidManifest.xml")

# 2. Update mission_screen.dart
dart_path = os.path.join('flutter_app', 'lib', 'screens', 'mission_screen.dart')
if os.path.exists(dart_path):
    with open(dart_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Replace final String _googleMapsApiKey = "YOUR_KEY_HERE";
    content = re.sub(
        r'final String _googleMapsApiKey = ".*?";',
        f'final String _googleMapsApiKey = "{maps_key}";',
        content
    )
    with open(dart_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(" - Updated mission_screen.dart")

# 3. Update alert_server.py
py_path = os.path.join('Arlert_BE', 'alert_server.py')
if os.path.exists(py_path):
    with open(py_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Replace api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    content = re.sub(
        r'api_key = os\.environ\.get\("GOOGLE_MAPS_API_KEY", ".*?"\)',
        f'api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "{maps_key}")',
        content
    )
    with open(py_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(" - Updated alert_server.py")

print("✅ Successfully synced API keys to all files.")
