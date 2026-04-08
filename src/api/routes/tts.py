"""
TTS 관련 HTTP 엔드포인트.
POST /api/tts/clone-voice — ElevenLabs 보이스 클론 생성
POST /api/tts/speak       — ElevenLabs TTS 음성 합성 (접근성 낭독용)
"""

from __future__ import annotations

import asyncio
import io
import logging
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.config import ELEVENLABS_API_KEY, TMP_DIR, is_dev_mode
from core.exceptions import TTSGenerationError
from services.static_tts_cache import StaticTTSAudioCache
from services.tts_edge import DEFAULT_VOICE as EDGE_DEFAULT_VOICE
from services.tts_edge import EdgeTTSEngine
from services.tts_elevenlabs import ElevenLabsTTS

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/tts')
static_tts_cache = StaticTTSAudioCache()


def _append_missing_text_once(log_path: Path, text: str) -> None:
    """같은 누락 문장이 반복 기록되지 않도록 로그를 유일값으로 유지한다."""
    existing = set()
    if log_path.exists():
        existing = {
            line.strip()
            for line in log_path.read_text(encoding='utf-8').splitlines()
            if line.strip()
        }
    if text in existing:
        return
    existing.add(text)
    log_path.write_text('\n'.join(sorted(existing)) + '\n', encoding='utf-8')


class VoiceCloneResponse(BaseModel):
    """보이스 클론 생성 응답."""

    voice_id: str
    voice_name: str


@router.get('/voices', response_model=dict[str, str])
def list_voices() -> dict[str, str]:
    """현재 ElevenLabs 계정의 화자 이름 -> ID 매핑을 반환한다."""
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=400, detail='ELEVENLABS_API_KEY가 설정되어 있지 않습니다.')

    try:
        return ElevenLabsTTS(api_key=ELEVENLABS_API_KEY)._get_voice_map()
    except TTSGenerationError as exc:
        logger.exception('[tts] list_voices failed')
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception('[tts] list_voices unexpected error')
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post('/clone-voice', response_model=VoiceCloneResponse)
async def clone_voice(
    name: Annotated[str, Form(description='생성할 클론 화자 이름')],
    files: Annotated[list[UploadFile], File(description='업로드할 WAV 파일 (1개 이상)')],
) -> VoiceCloneResponse:
    """
    WAV 파일을 ElevenLabs에 업로드해 인스턴트 보이스 클론을 생성한다.

    Args:
        name: 클론 화자 이름
        files: WAV 파일 리스트 (multipart/form-data)

    Returns:
        VoiceCloneResponse: 생성된 voice_id 및 이름

    Raises:
        HTTPException 400: 파일 미제공 또는 API 키 미설정
        HTTPException 500: ElevenLabs API 호출 실패
    """
    if not files:
        raise HTTPException(status_code=400, detail='WAV 파일을 1개 이상 업로드해야 합니다.')
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=400, detail='ELEVENLABS_API_KEY가 설정되어 있지 않습니다.')

    tmp_paths: list[Path] = []
    try:
        # 업로드 파일을 임시 경로에 저장
        for upload in files:
            suffix = Path(upload.filename or 'voice.wav').suffix or '.wav'
            tmp_path = TMP_DIR / f'clone_{uuid.uuid4().hex}{suffix}'
            tmp_path.write_bytes(await upload.read())
            tmp_paths.append(tmp_path)

        tts = ElevenLabsTTS(api_key=ELEVENLABS_API_KEY)
        voice_id = tts.clone_voice(name=name, wav_paths=tmp_paths)

    except TTSGenerationError as exc:
        logger.exception('[tts] clone_voice failed')
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception('[tts] clone_voice unexpected error')
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        for p in tmp_paths:
            p.unlink(missing_ok=True)

    return VoiceCloneResponse(voice_id=voice_id, voice_name=name)


class SpeakRequest(BaseModel):
    """접근성 낭독 TTS 요청."""

    text: str
    voice_name: str = 'JiYeong Kang'
    allow_generation: bool = False


@router.post('/speak')
async def speak_text(req: SpeakRequest) -> StreamingResponse:
    """
    텍스트를 ElevenLabs TTS로 변환해 오디오 스트림을 반환한다.
    Streamlit 접근성 낭독(speak) 용도.

    Args:
        req: 낭독할 텍스트와 화자 이름

    Returns:
        StreamingResponse: MP3 오디오 스트림

    Raises:
        HTTPException 400: API 키 미설정
        HTTPException 500: TTS 합성 실패
    """
    if not is_dev_mode() and not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=400, detail='ELEVENLABS_API_KEY가 설정되어 있지 않습니다.')

    try:
        cached_audio = static_tts_cache.find_audio(req.text, req.voice_name)
        if cached_audio is not None:
            logger.info(
                '[tts] static_cache_hit voice=%s text_len=%d path=%s',
                req.voice_name,
                len(req.text),
                cached_audio.audio_path,
            )
            return StreamingResponse(
                io.BytesIO(cached_audio.audio_path.read_bytes()),
                media_type=cached_audio.media_type,
                headers={'X-ReadMate-TTS-Source': 'static-cache'},
            )

        if not req.allow_generation:
            logger.warning('[tts] missing static text: %r', req.text)

            log_path = Path('data/static_tts/missing_texts.log')
            log_path.parent.mkdir(parents=True, exist_ok=True)
            _append_missing_text_once(log_path, req.text)

            raise HTTPException(
                status_code=400,
                detail='이 텍스트는 정적 TTS가 존재하지 않으며, 동적 생성(allow_generation)이 허용되지 않았습니다.'
            )

        if is_dev_mode():
            tts_engine = EdgeTTSEngine()
            result = tts_engine.synthesize(req.text, EDGE_DEFAULT_VOICE)
            tts_source = 'edge'
        else:
            tts_engine = ElevenLabsTTS(api_key=ELEVENLABS_API_KEY)
            result = tts_engine.synthesize(req.text, req.voice_name)
            tts_source = 'elevenlabs'

        audio_path = Path(result.audio_path)
        audio_bytes = audio_path.read_bytes()
        audio_path.unlink(missing_ok=True)
    except TTSGenerationError as exc:
        logger.exception('[tts] speak failed')
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception('[tts] speak unexpected error')
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type='audio/mpeg',
        headers={'X-ReadMate-TTS-Source': tts_source},
    )
