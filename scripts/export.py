import lac
from lac.model import LAC
import math

import torch
import torch.nn as nn
import nn_tilde
import cached_conv as cc
import argbind

def next_power_of_2(x):  
    return 1 if x == 0 else (2**(x - 1).bit_length()) 

class ScriptedLAC(nn_tilde.Module):

    def __init__(self,
                 pretrained: LAC,
                 stereo: bool = False,
                 target_sr: bool = None) -> None:
        super().__init__()
        self.stereo = stereo
        self.model = pretrained

        channels = ["(L)", "(R)"] if stereo else ["(mono)"]

        self.register_buffer("hop_length", torch.tensor(self.model.hop_length))

        hl = self.model.hop_length.item()
        
        if 8192 % hl != 0:
            self.register_method(
                
            )
        else:
            z_ratio = hl
            print(f"z_ratio: {z_ratio}")
            self.register_method(
                "encode",
                in_channels=1,
                in_ratio=1,
                out_channels=self.model.n_codebooks,
                out_ratio=z_ratio,
                input_labels=['(signal) Input audio signal'],
                output_labels=[
                    f'(signal) codebook {i}'
                    for i in range(self.model.n_codebooks)
                ],
            )
            self.register_method(
                "decode",
                in_channels=self.model.quantizer.n_codebooks,
                in_ratio=z_ratio,
                out_channels=2 if stereo else 1,
                out_ratio=1,
                input_labels=[
                    f'(signal) codebook {i}'
                    for i in range(self.model.n_codebooks)
                ],
                output_labels=[
                    f'(signal) Reconstructed audio signal {channel}'
                    for channel in channels
                ],
            )

        self.trim_len = torch.jit.Attribute(0, int)

    @torch.jit.export
    def encode(self, x):
        # x is (b, c, t)
        # TODO: resample here
        out = self.model.encode(x, sample_rate=None)
        codes = out["codes"]
        self.trim_len = int(out["length"].item())
        return codes.float()

    @torch.jit.export
    def decode(self, codes):

        z, _, _ = self.model.quantizer.from_codes(codes.long())

        y = self.model.decode(z, 
            length=None if self.trim_len == 0 else self.trim_len
        )["audio"]

        # resample back to original sample rate
        # TODO
        return y

@argbind.bind(without_prefix=True)
def export(ckpt: str = None, output: str = "lac.ts"):
    assert ckpt is not None, "weights_path must be specified"

    cc.use_cached_conv(True)

    if ckpt is None:
        model = LAC()
    else:
        model = LAC.load(ckpt)

    model.eval()
    print("warmup pass")

    x = torch.zeros(1, 1, 2**14)
    model(x)

    for m in model.modules():
        if hasattr(m, "weight_g"):
            nn.utils.remove_weight_norm(m)  

    scriptedmodel  = ScriptedLAC(model)
    scriptedmodel.export_to_ts(output)

    print("done")



if __name__ == "__main__":
    args = argbind.parse_args()

    with argbind.scope(args):
        export()