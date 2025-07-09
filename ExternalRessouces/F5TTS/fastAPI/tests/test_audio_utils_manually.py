# test_audio_utils_manually.py
import numpy as np
import audio_utils
import wave # For inspecting output

SAMPLE_RATE = 24000
OVERLAP_MS = 150

# Calculate overlap_samples for the test script's context
test_overlap_samples = int(SAMPLE_RATE * OVERLAP_MS / 1000) if OVERLAP_MS > 0 else 0


# Test 1: Mixing two simple sine waves
print("--- Test 1: Mixing Sine Waves ---")
duration1 = 1.0  # seconds
frequency1 = 440  # A4
t1 = np.linspace(0, duration1, int(SAMPLE_RATE * duration1), endpoint=False)
chunk1 = 0.5 * np.sin(2 * np.pi * frequency1 * t1)

duration2 = 1.5  # seconds
frequency2 = 660  # E5
t2 = np.linspace(0, duration2, int(SAMPLE_RATE * duration2), endpoint=False)
chunk2 = 0.3 * np.sin(2 * np.pi * frequency2 * t2)

mixed_audio = audio_utils.mix_audio_chunks_with_crossfade([chunk1, chunk2], SAMPLE_RATE, OVERLAP_MS)

if mixed_audio is not None:
    print(f"Mixed audio length: {len(mixed_audio)} samples")
    # Calculate expected length based on whether an overlap actually occurred
    overlap_occurred_in_mix = (
        OVERLAP_MS > 0 and 
        len(chunk1) > test_overlap_samples and 
        len(chunk2) > test_overlap_samples
    )
    expected_len_approx = len(chunk1) + len(chunk2) - (test_overlap_samples if overlap_occurred_in_mix else 0)
    
    print(f"Expected approximate length: {expected_len_approx} samples (using test_overlap_samples: {test_overlap_samples})")
    assert abs(len(mixed_audio) - expected_len_approx) < 5, \
        f"Mixed length mismatch. Got: {len(mixed_audio)}, Expected: {expected_len_approx}"

    wav_bytes = audio_utils.convert_float32_to_wav_bytes(mixed_audio, SAMPLE_RATE)
    with open("mixed_sines.wav", "wb") as f:
        f.write(wav_bytes)
    print("Saved mixed_sines.wav. Listen to verify crossfade.")
else:
    print("ERROR: Mixing sine waves resulted in None.")


# Test 2: Mixing with None or empty chunks
print("\n--- Test 2: Mixing with None/Empty ---")
# We expect the same result as mixing chunk1 and chunk2
expected_mixed_with_none_len = len(mixed_audio) # From Test 1 successful mix

mixed_with_none = audio_utils.mix_audio_chunks_with_crossfade([chunk1, None, chunk2, np.array([])], SAMPLE_RATE, OVERLAP_MS)
if mixed_with_none is not None:
    assert len(mixed_with_none) == expected_mixed_with_none_len, "Mixing with None/Empty failed (length mismatch)"
    print("Mixing with None/Empty chunks successful.")
else:
    print("ERROR: Mixing with None/Empty resulted in None (it should have mixed chunk1 and chunk2).")

# Test 3: Single chunk
print("\n--- Test 3: Single Chunk ---")
single_mixed = audio_utils.mix_audio_chunks_with_crossfade([chunk1], SAMPLE_RATE, OVERLAP_MS)
if single_mixed is not None:
    assert np.array_equal(single_mixed, chunk1), "Single chunk mixing failed"
    print("Single chunk processing successful.")
else:
    print("ERROR: Single chunk resulted in None.")

# Test 4: No valid chunks
print("\n--- Test 4: No Valid Chunks ---")
no_chunks_mixed = audio_utils.mix_audio_chunks_with_crossfade([None, np.array([])], SAMPLE_RATE, OVERLAP_MS)
assert no_chunks_mixed is None, "No valid chunks should result in None"
print("Processing no valid chunks successful (returned None).")

# Test 5: WAV conversion of silent audio
print("\n--- Test 5: Silent WAV ---")
silent_wav_bytes = audio_utils.convert_float32_to_wav_bytes(None, SAMPLE_RATE)
assert len(silent_wav_bytes) > 40, "Silent WAV bytes seem too short" # WAV header is ~44 bytes
with open("silent_test.wav", "wb") as f:
    f.write(silent_wav_bytes)
print("Saved silent_test.wav. Should be a very short silent audio file.")
# Verify its properties
try:
    with wave.open("silent_test.wav", 'rb') as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == SAMPLE_RATE
        assert wf.getsampwidth() == 2
        print("Silent WAV properties verified.")
except wave.Error as e:
    print(f"ERROR verifying silent WAV: {e}")


# Test 6: Chunks too short for full overlap
print("\n--- Test 6: Chunks too short for full overlap ---")
short_chunk1 = chunk1[:test_overlap_samples // 2] # Shorter than overlap
short_chunk2 = chunk2[:test_overlap_samples // 2] # Shorter than overlap
mixed_short_chunks = audio_utils.mix_audio_chunks_with_crossfade([short_chunk1, short_chunk2], SAMPLE_RATE, OVERLAP_MS)
if mixed_short_chunks is not None:
    # In this case, they should just be concatenated as no crossfade can occur
    expected_short_len = len(short_chunk1) + len(short_chunk2)
    assert len(mixed_short_chunks) == expected_short_len, \
        f"Short chunk mix length mismatch. Got {len(mixed_short_chunks)}, Expected {expected_short_len}"
    print("Mixing short chunks (concatenation) successful.")
    wav_bytes_short = audio_utils.convert_float32_to_wav_bytes(mixed_short_chunks, SAMPLE_RATE)
    with open("mixed_short_chunks.wav", "wb") as f:
        f.write(wav_bytes_short)
    print("Saved mixed_short_chunks.wav.")

else:
    print("ERROR: Mixing short chunks resulted in None.")


print("\nAudio utils manual checks complete.")