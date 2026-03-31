from pathlib import Path

from pyprojroot import here

root = here()


def model_path(file_name):
    model_path = root / 'data' / 'models'
    Path(model_path).mkdir(parents=True, exist_ok=True)

    return model_path / file_name


def data_path():
    data_path = root / 'data'
    Path(data_path).mkdir(parents=True, exist_ok=True)

    return data_path


def images_path():
    return data_path() / 'images'


def keys_path():
    return root / 'keys'
