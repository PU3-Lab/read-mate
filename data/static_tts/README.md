Static TTS cache

Place pre-generated prompt audio files in this directory and register them in `manifest.json`.

Manifest format:

```json
{
  "entries": [
    {
      "text": "ReadMate입니다. Tab 키를 눌러 기능을 선택하세요.",
      "audio_file": "home_intro.mp3",
      "voice_name": "JiYeong Kang"
    },
    {
      "text": "기능 선택 화면으로 돌아갑니다.",
      "audio_file": "common/back_home.mp3",
      "voice_name": "*"
    }
  ]
}
```

Notes:

- `text`: exact prompt text used in `speak(...)`. Whitespace is normalized before matching.
- `audio_file`: relative path from `data/static_tts/`, or an absolute path.
- `voice_name`: optional. Use `*` to match every voice.
- When a manifest entry matches, `/api/tts/speak` streams the audio file instead of calling ElevenLabs.
