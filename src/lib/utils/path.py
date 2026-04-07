from pathlib import Path

from pyprojroot import here

root = here()


def model_path(file_name: str = '') -> Path:
    _model_path = root / 'data' / 'models'
    _model_path.mkdir(parents=True, exist_ok=True)
    return _model_path / file_name if file_name else _model_path


def embeddings_path() -> Path:
    _emb_path = model_path() / 'voices'
    _emb_path.mkdir(parents=True, exist_ok=True)
    return _emb_path


def data_path() -> Path:
    data_path = root / 'data'
    Path(data_path).mkdir(parents=True, exist_ok=True)

    return data_path


def tmp_path() -> Path:
    _tmp_path = data_path() / 'tmp'
    _tmp_path.mkdir(parents=True, exist_ok=True)

    return _tmp_path


def voices_path() -> Path:
    _voices_path = data_path() / 'voices'
    _voices_path.mkdir(parents=True, exist_ok=True)

    return _voices_path


def static_tts_path(file_name: str = '') -> Path:
    _static_tts_path = data_path() / 'static_tts'
    _static_tts_path.mkdir(parents=True, exist_ok=True)
    return _static_tts_path / file_name if file_name else _static_tts_path


def images_path() -> Path:
    return data_path() / 'images'


def keys_path() -> Path:
    return root / 'keys'
