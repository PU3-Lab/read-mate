import requests
import sys

def test_speak():
    url = "http://localhost:28765/api/tts/speak"
    payload = {
        "text": "테스트입니다.",
        "voice_name": "JiYeong Kang",
        "allow_generation": True
    }
    try:
        resp = requests.post(url, json=payload, timeout=5)
        print(f"Status Code: {resp.status_code}")
        if resp.ok:
            print("Success! Audio received.")
            print(f"Content Type: {resp.headers.get('Content-Type')}")
            print(f"Content Length: {len(resp.content)} bytes")
        else:
            print(f"Error: {resp.text}")
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    test_speak()
