"""
HWP(한글 파일) 텍스트 추출 엔진 구현.
pyhwp 우선, LibreOffice 폴백 전략으로 텍스트형/이미지형 HWP 모두 처리.
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from src.models.schemas import HWPResult
from src.services.base import BasePDF, BaseHWP

logger = logging.getLogger(__name__)

# LibreOffice 가능한 설치 경로 (OS별)
_LIBREOFFICE_PATHS = [
    'C:/Program Files/LibreOffice/program/soffice.exe',      # Windows
    'C:/Program Files (x86)/LibreOffice/program/soffice.exe',
    '/usr/bin/libreoffice',                                  # Linux
    '/usr/bin/soffice',
    '/Applications/LibreOffice.app/Contents/MacOS/soffice',  # macOS
]

_PYHWP_MIN_TEXT = 100  # pyhwp 결과가 이 미만이면 이미지형으로 간주


class HWPEngine(BaseHWP):
  """
  HWP(한글 워드프로세서) 파일 텍스트 추출 엔진.
  pyhwp 우선 시도, 실패 또는 텍스트 부족 시 LibreOffice PDF 변환 후
  PyPDFEngine으로 처리하는 폴백 전략 사용.
  """

  def __init__(self, pdf_fallback: BasePDF) -> None:
    """
    Args:
        pdf_fallback: LibreOffice 변환 후 PDF 처리에 사용할 엔진
    """
    self._pdf_engine = pdf_fallback
    self._libreoffice_path: str | None = self._find_libreoffice()
    if self._libreoffice_path:
      logger.info('LibreOffice 발견: %s', self._libreoffice_path)
    else:
      logger.warning('LibreOffice 미설치 — HWP 이미지형 처리 불가')

  def _find_libreoffice(self) -> str | None:
    """시스템에서 LibreOffice 실행 파일 경로 탐색."""
    for path in _LIBREOFFICE_PATHS:
      if Path(path).exists():
        return path
    return None

  def extract(self, hwp_bytes: bytes) -> HWPResult:
    """
    HWP 파일에서 텍스트 추출.

    1단계: pyhwp로 텍스트 추출 시도
    2단계: pyhwp 실패 또는 텍스트 부족 시
           LibreOffice → PDF → PyPDFEngine

    Args:
        hwp_bytes: HWP 원본 바이트

    Returns:
        HWPResult: 추출 텍스트, 페이지 수, 이미지형 여부, 추출 방법

    Raises:
        RuntimeError: pyhwp, LibreOffice 모두 실패한 경우
    """
    # 1단계: pyhwp 시도
    text = self._extract_with_pyhwp(hwp_bytes)
    if text and len(text) >= _PYHWP_MIN_TEXT:
      logger.info('pyhwp 성공: text_len=%d', len(text))
      return HWPResult(
          text=text,
          page_count=1,
          is_image_based=False,
          extraction_method='pyhwp',
      )

    # 2단계: LibreOffice 폴백
    if self._libreoffice_path:
      logger.info('pyhwp 부족/실패, LibreOffice 폴백 시작')
      return self._extract_with_libreoffice(hwp_bytes)

    # 모두 실패
    raise RuntimeError(
        'HWP 추출 실패: pyhwp 텍스트 부족 및 LibreOffice 미설치'
    )

  def _extract_with_pyhwp(self, hwp_bytes: bytes) -> str | None:
    """
    pyhwp 라이브러리로 텍스트 추출 시도.
    hwp5txt CLI 래퍼 방식으로 처리.
    실패 시 None 반환.
    """
    try:
      with tempfile.NamedTemporaryFile(
          suffix='.hwp', delete=False
      ) as tmp:
        tmp.write(hwp_bytes)
        tmp_path = tmp.name

      try:
        result = subprocess.run(
            ['hwp5txt', tmp_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=30,
        )
        if result.returncode == 0:
          text = result.stdout.strip()
          logger.info('pyhwp 추출 완료: text_len=%d', len(text))
          return text
        else:
          logger.warning(
              'hwp5txt 실패 (code=%d): %s', result.returncode, result.stderr
          )
          return None
      finally:
        os.unlink(tmp_path)
    except FileNotFoundError:
      logger.warning('hwp5txt 명령어 미발견 (pyhwp 미설치?)')
      return None
    except subprocess.TimeoutExpired:
      logger.warning('hwp5txt 타임아웃 (30초)')
      return None
    except Exception as e:
      logger.warning('pyhwp 추출 중 예외: %s', e)
      return None

  def _extract_with_libreoffice(self, hwp_bytes: bytes) -> HWPResult:
    """
    LibreOffice로 HWP → PDF 변환 후 pdf_fallback 엔진으로 처리.
    임시 디렉토리를 사용해 변환 파일을 생성, 완료 후 정리.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
      hwp_path = Path(tmpdir) / 'input.hwp'
      hwp_path.write_bytes(hwp_bytes)

      try:
        subprocess.run(
            [
                self._libreoffice_path,
                '--headless',
                '--convert-to',
                'pdf',
                '--outdir',
                tmpdir,
                str(hwp_path),
            ],
            check=True,
            timeout=60,
            capture_output=True,
        )
      except subprocess.TimeoutExpired:
        raise RuntimeError('LibreOffice 변환 타임아웃 (60초)')
      except subprocess.CalledProcessError as e:
        raise RuntimeError(f'LibreOffice 변환 실패: {e.stderr.decode()}')
      except Exception as e:
        raise RuntimeError(f'LibreOffice 호출 실패: {e}')

      pdf_path = hwp_path.with_suffix('.pdf')
      if not pdf_path.exists():
        raise RuntimeError('LibreOffice 변환 후 PDF 파일 미생성')

      # PDF 처리
      pdf_result = self._pdf_engine.extract(pdf_path.read_bytes())
      method = (
          'libreoffice_ocr'
          if pdf_result.is_scanned
          else 'libreoffice_pdf'
      )

      logger.info(
          'LibreOffice 변환 완료: method=%s, pages=%d, is_scanned=%s',
          method,
          pdf_result.page_count,
          pdf_result.is_scanned,
      )

      return HWPResult(
          text=pdf_result.text,
          page_count=pdf_result.page_count,
          is_image_based=pdf_result.is_scanned,
          extraction_method=method,
      )
