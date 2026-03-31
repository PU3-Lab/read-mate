import sys

import torch

CPU = 'cpu'


def available_device():
    device = CPU
    if sys.platform == 'win32' or sys.platform == 'linux':
        device = 'cuda' if torch.cuda.is_available() else CPU
    else:
        device = 'mps' if torch.backends.mps.is_available() else CPU

    print(f'using {device}')
    return device
