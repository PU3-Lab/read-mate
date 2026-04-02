"""Vendored Zonos backbone package.

Upstream `zonos` 0.1.0 wheels currently omit the `zonos.backbone` subpackage,
which breaks `from zonos.model import Zonos` under `uv run` auto-sync.
This namespace package fragment restores the missing modules locally.
"""

BACKBONES = {}

try:
    from ._mamba_ssm import MambaSSMZonosBackbone

    BACKBONES['mamba_ssm'] = MambaSSMZonosBackbone
except ImportError:
    pass

from ._torch import TorchZonosBackbone

BACKBONES['torch'] = TorchZonosBackbone
