"""Optional mamba-ssm Zonos backbone.

The import is intentionally isolated because most local environments in this
project will not have the compile-only `mamba-ssm` extras installed.
"""

from __future__ import annotations

import torch
import torch.nn as nn
from mamba_ssm.models.mixer_seq_simple import create_block
from mamba_ssm.ops.triton.layer_norm import layer_norm_fn
from zonos.config import BackboneConfig, InferenceParams


class MambaSSMZonosBackbone(nn.Module):
    """Hybrid/mamba Zonos backbone."""

    supported_architectures = ['transformer', 'hybrid']

    def __init__(self, config: BackboneConfig) -> None:
        """Mamba 기반 블록 스택을 구성한다."""
        super().__init__()
        self.config = config
        self.layers = nn.ModuleList(
            [
                create_block(
                    d_model=config.d_model,
                    d_intermediate=(
                        config.d_intermediate
                        if i not in config.attn_layer_idx
                        else config.attn_mlp_d_intermediate
                    ),
                    ssm_cfg=config.ssm_cfg,
                    layer_idx=i,
                    attn_layer_idx=config.attn_layer_idx,
                    attn_cfg=config.attn_cfg,
                    norm_epsilon=config.norm_epsilon,
                    residual_in_fp32=config.residual_in_fp32,
                    fused_add_norm=True,
                    rms_norm=config.rms_norm,
                )
                for i in range(config.n_layer)
            ]
        )
        self.norm_f = nn.LayerNorm(config.d_model, eps=config.norm_epsilon)

    def allocate_inference_cache(
        self,
        batch_size: int,
        max_seqlen: int,
        dtype: torch.dtype = torch.bfloat16,
    ) -> dict[int, object]:
        """레이어별 mamba inference cache를 준비한다."""
        return {
            i: layer.allocate_inference_cache(batch_size, max_seqlen, dtype=dtype)
            for i, layer in enumerate(self.layers)
        }

    def forward(
        self,
        hidden_states: torch.Tensor,
        inference_params: InferenceParams | None = None,
    ) -> torch.Tensor:
        """Mamba 블록을 순차 적용한다."""
        residual = None
        for layer in self.layers:
            hidden_states, residual = layer(hidden_states, residual, inference_params)

        return layer_norm_fn(
            hidden_states,
            self.norm_f.weight,
            self.norm_f.bias,
            residual,
            eps=self.norm_f.eps,
            residual_in_fp32=self.config.residual_in_fp32,
            is_rms_norm=self.config.rms_norm,
        )
