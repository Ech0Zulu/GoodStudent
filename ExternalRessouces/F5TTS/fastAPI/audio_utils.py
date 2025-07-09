# audio_utils.py
import numpy as np
import wave
import io
from typing import List, Optional

def mix_audio_chunks_with_crossfade(
    audio_chunks: List[Optional[np.ndarray]], 
    sample_rate: int, 
    overlap_ms: int = 150
) -> Optional[np.ndarray]:
    """
    Mixes a list of audio chunks (NumPy float32 arrays) with crossfading.
    Filters out None or empty chunks.
    """
    # Filter out None or empty chunks
    valid_chunks = [chunk for chunk in audio_chunks if chunk is not None and chunk.size > 0]

    if not valid_chunks:
        return None
    if len(valid_chunks) == 1:
        return valid_chunks[0]

    overlap_samples = int(sample_rate * overlap_ms / 1000)
    
    # Ensure curves are only calculated if overlap_samples > 0
    fade_out_curve = np.linspace(1.0, 0.0, overlap_samples, dtype=np.float32) if overlap_samples > 0 else np.array([])
    fade_in_curve = np.linspace(0.0, 1.0, overlap_samples, dtype=np.float32) if overlap_samples > 0 else np.array([])

    mixed_audio = valid_chunks[0]
    for i in range(1, len(valid_chunks)):
        current_chunk = valid_chunks[i]
        
        if overlap_samples > 0 and mixed_audio.size > overlap_samples and current_chunk.size > overlap_samples:
            # Perform crossfade
            tail_of_previous = mixed_audio[-overlap_samples:]
            head_of_current = current_chunk[:overlap_samples]
            
            crossfaded_part = tail_of_previous * fade_out_curve + head_of_current * fade_in_curve
            
            mixed_audio = np.concatenate((
                mixed_audio[:-overlap_samples],
                crossfaded_part,
                current_chunk[overlap_samples:]
            ))
        else:
            # Not enough samples for overlap, or overlap_ms is 0, append directly
            mixed_audio = np.concatenate((mixed_audio, current_chunk))
            
    return mixed_audio

def convert_float32_to_wav_bytes(audio_data: np.ndarray, sample_rate: int, channels: int = 1) -> bytes:
    """
    Converts a NumPy array of float32 audio samples to WAV file bytes.
    Assumes audio_data is in the range [-1.0, 1.0].
    """
    if audio_data is None or audio_data.size == 0:
        # Create a very short silent WAV if no audio data
        sample_width = 2 # 16-bit
        num_frames = 10 # Arbitrary small number for a silent frame
        silence = np.zeros(num_frames, dtype=np.int16)
    else:
        # Normalize and convert float32 to int16
        # Ensure data is clipped to [-1, 1] to prevent overflow when converting to int16
        audio_data_clipped = np.clip(audio_data, -1.0, 1.0)
        int16_samples = (audio_data_clipped * 32767.0).astype(np.int16)
        sample_width = 2 # 16-bit
        num_frames = int16_samples.shape[0]
        sound_data = int16_samples.tobytes()

    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width) # 2 bytes for int16
        wf.setframerate(sample_rate)
        if audio_data is not None and audio_data.size > 0:
            wf.writeframes(sound_data)
        else:
            wf.writeframes(silence.tobytes())
            
    wav_bytes = wav_buffer.getvalue()
    return wav_bytes

# Optional MP3 conversion (requires pydub and ffmpeg/libmp3lame)
# from pydub import AudioSegment
# def convert_wav_bytes_to_mp3_bytes(wav_bytes: bytes, bitrate="128k") -> Optional[bytes]:
#     """Converts WAV bytes to MP3 bytes using pydub."""
#     if not wav_bytes:
#         return None
#     try:
#         audio_segment = AudioSegment.from_wav(io.BytesIO(wav_bytes))
#         mp3_buffer = io.BytesIO()
#         audio_segment.export(mp3_buffer, format="mp3", bitrate=bitrate)
#         return mp3_buffer.getvalue()
#     except Exception as e:
#         print(f"AUDIO_UTILS: ERROR - Failed to convert WAV to MP3: {e}")
#         return None