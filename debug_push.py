"""Test script: simulate an alert and check what the backend does with push notifications."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import asyncio
import httpx

async def main():
    # 1. Trigger a test alert on cam01
    alert = {
        'time': '2026-06-28 00:05:00',
        'location': 'cam01',
        'lat': 16.0381577,
        'lng': 108.2392327,
        'type': 'accident',
        'video': 'fake_test.mp4',
        'stream': 'http://localhost:8889/cam01/whep',
        'camera_id': 'cam01'
    }
    
    print("=== Sending test alert to /alert ===")
    async with httpx.AsyncClient() as client:
        resp = await client.post('http://localhost:8000/alert', json=alert, timeout=30.0)
        print(f"Response: {resp.status_code} - {resp.json()}")
    
    print("\n=== Now check server console for push notification logs ===")

asyncio.run(main())
