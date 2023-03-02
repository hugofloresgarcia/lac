import math
from pathlib import Path

import torch
import tqdm
from audiotools import AudioSignal


class CodecMixin:
    EXT = ".lac"
    
    @torch.no_grad()
    def encode(
        self,
        audio_path_or_signal,
        overlap_win_duration: float = 5.0,
        verbose: bool = False,
        normalize_db: float = -16,
        match_input_db: bool = False,
        mono: bool = False,
        **kwargs,
    ):
        self.eval()
        audio_signal = audio_path_or_signal
        if isinstance(audio_signal, (str, Path)):
            audio_signal = AudioSignal.load_from_file_with_ffmpeg(str(audio_signal))
        
        if mono:
            audio_signal = audio_signal.to_mono()

        audio_signal = audio_signal.clone()
        audio_signal = audio_signal.ffmpeg_resample(self.sample_rate)

        original_length = audio_signal.signal_length
        input_db = audio_signal.ffmpeg_loudness()

        # Fix overlap window so that it's divisible by 4 in # of samples
        sr = audio_signal.sample_rate
        overlap_win_duration = ((overlap_win_duration * sr) // 4) * 4
        overlap_win_duration = overlap_win_duration / sr

        if normalize_db is not None:
            audio_signal.normalize(normalize_db)
        audio_signal.ensure_max_of_audio()
        overlap_hop_duration = overlap_win_duration * 0.5
        boundary = int(overlap_hop_duration * self.sample_rate / 2)
        do_overlap_and_add = audio_signal.signal_duration > overlap_win_duration

        nb, nac, nt = audio_signal.audio_data.shape
        audio_signal.audio_data = audio_signal.audio_data.reshape(nb * nac, 1, nt)

        if do_overlap_and_add:
            pad_length = (
                math.ceil(audio_signal.signal_duration / overlap_win_duration)
                * overlap_win_duration
            )
            audio_signal.zero_pad_to(int(pad_length * sr))
            audio_signal = audio_signal.collect_windows(
                overlap_win_duration, overlap_hop_duration
            )

        range_fn = range if not verbose else tqdm.trange
        for i in range_fn(audio_signal.batch_size):
            signal_from_batch = AudioSignal(
                audio_signal.audio_data[i, ...], audio_signal.sample_rate
            )
            signal_from_batch.to(self.device)
            _output = self.forward(
                signal_from_batch.audio_data, signal_from_batch.sample_rate, **kwargs
            )

            _output = _output["audio"].detach()
            _output_signal = AudioSignal(_output, self.sample_rate).to(self.device)
            audio_signal.audio_data[i] = _output_signal.audio_data.cpu()

        enhanced = audio_signal
        enhanced._loudness = None
        enhanced.stft_data = None

        if do_overlap_and_add:
            enhanced.trim(boundary, boundary)
            enhanced.audio_data = enhanced.audio_data.reshape(nb, nac, -1)
            enhanced.trim(boundary, boundary)
            enhanced.truncate_samples(nt)
        enhanced.audio_data = enhanced.audio_data.reshape(nb, nac, nt)

        if match_input_db:
            enhanced.ffmpeg_loudness()
            enhanced = enhanced.normalize(input_db)

        enhanced.truncate_samples(original_length)
        return enhanced
