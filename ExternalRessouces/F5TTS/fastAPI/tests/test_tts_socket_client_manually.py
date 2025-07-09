# test_tts_socket_client_manually.py
import tts_socket_client
import audio_utils # For saving the result of synthesize_text_via_socket (which returns np arrays)
import numpy as np

F5TTS_BACKEND_IP = "127.0.0.1"  # Or your F5TTS backend IP
F5TTS_BACKEND_PORT = 9998       # Or your F5TTS backend port
SAMPLE_RATE = 24000 # Must match what the backend produces for saving correctly

# Test 1: Sentence splitting
print("--- Test 1: Sentence Splitting ---")
text1 = "Hello world. This is a test!"
sentences1 = tts_socket_client.split_text_into_sentences(text1)
print(f"Sentences from '{text1}': {sentences1}")
assert sentences1 == ["Hello world.", "This is a test!"], "Sentence split 1 failed"

text2 = "One sentence only."
sentences2 = tts_socket_client.split_text_into_sentences(text2)
print(f"Sentences from '{text2}': {sentences2}")
assert sentences2 == ["One sentence only."], "Sentence split 2 failed"

text3 = "Empty.  "
sentences3 = tts_socket_client.split_text_into_sentences(text3)
print(f"Sentences from '{text3}': {sentences3}")
assert sentences3 == ["Empty."], "Sentence split 3 failed"

text4 = ""
sentences4 = tts_socket_client.split_text_into_sentences(text4)
print(f"Sentences from '{text4}': {sentences4}")
assert sentences4 == [], "Sentence split 4 failed"
print("Sentence splitting tests passed.")


# Test 2: Full synthesis via socket (assuming F5TTS backend is running)
print("\n--- Test 2: Full Synthesis via Socket ---")
test_text_full = "Hello from the socket client. This is the second sentence."

try:
    raw_chunks = tts_socket_client.synthesize_text_via_socket(
        test_text_full, F5TTS_BACKEND_IP, F5TTS_BACKEND_PORT
    )

    if raw_chunks:
        print(f"Received {len(raw_chunks)} raw chunks.")
        # Filter out Nones for mixing if any chunk failed
        valid_chunks_for_mixing = [ch for ch in raw_chunks if ch is not None and ch.size > 0]
        
        if valid_chunks_for_mixing:
            # Mix them using audio_utils to test saving a complete audio
            # (tts_socket_client itself doesn't do the mixing)
            mixed_audio_np = audio_utils.mix_audio_chunks_with_crossfade(
                valid_chunks_for_mixing, SAMPLE_RATE, overlap_ms=150
            )
            if mixed_audio_np is not None:
                wav_output_bytes = audio_utils.convert_float32_to_wav_bytes(mixed_audio_np, SAMPLE_RATE)
                with open("socket_client_output.wav", "wb") as f:
                    f.write(wav_output_bytes)
                print("Saved socket_client_output.wav. Listen to verify.")
            else:
                print("WARN: Mixing resulted in no audio, though some chunks might have been received.")
        else:
            print("WARN: No valid audio chunks received from synthesize_text_via_socket.")
    else:
        print("WARN: synthesize_text_via_socket returned an empty list or None (could be connection issue or no sentences).")

except tts_socket_client.TTSSocketError as e:
    print(f"ERROR: TTSSocketError during full synthesis test: {e}")
except Exception as e:
    print(f"ERROR: Unexpected exception during full synthesis test: {e}")

# Test 3: Connection to a non-existent server (EXPECT FAILURE)
print("\n--- Test 3: Connection to Non-existent Server ---")
try:
    tts_socket_client.synthesize_text_via_socket(
        "Test.", "127.0.0.1", 12345 # Bogus port
    )
    print("ERROR: Test 3 FAILED - Expected TTSSocketError for bad port.")
except tts_socket_client.TTSSocketError:
    print("Test 3 PASSED - Correctly raised TTSSocketError for bad port.")
except Exception as e:
    print(f"ERROR: Test 3 FAILED - Unexpected error for bad port: {e}")

print("\nTTS Socket Client manual tests complete.")