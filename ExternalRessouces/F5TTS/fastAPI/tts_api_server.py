# tts_api_server.py
import fastapi
from fastapi.responses import StreamingResponse, Response
import uvicorn
import io
from typing import Optional, Dict

# Import from our other modules
import tts_socket_client
import audio_utils

# Configuration (can be moved to a config file or env vars later)
F5TTS_BACKEND_IP = "127.0.0.1"  # IP of your actual F5TTS engine
F5TTS_BACKEND_PORT = 9998       # Port of your actual F5TTS engine
API_SAMPLE_RATE = 24000         # Sample rate for the output WAV
API_OVERLAP_MS = 150            # Crossfade duration

app = fastapi.FastAPI()

# In-memory cache (simple example, consider Redis or other for production)
# Cache key: text, Cache value: wav_bytes
# This is a very basic cache, not thread-safe for updates without locks if multiple
# gunicorn/uvicorn workers are used. For single worker, it's fine.
# For simplicity, we'll avoid complex cache eviction policies here.
TTS_CACHE: Dict[str, bytes] = {}
CACHE_MAX_SIZE = 100 # Max number of items in cache


@app.post("/speak/", response_class=Response)
async def speak_text(text_request: str = fastapi.Body(..., embed=True, description="Text to synthesize.")):
    """
    Receives text, synthesizes it to audio using the F5TTS backend,
    and returns the audio as WAV bytes.
    """
    if not text_request or not text_request.strip():
        return Response(content=b"Error: No text provided.", status_code=400, media_type="text/plain")

    # Check cache first
    if text_request in TTS_CACHE:
        print("API_SERVER: Cache hit!")
        wav_bytes = TTS_CACHE[text_request]
        return Response(content=wav_bytes, media_type="audio/wav")
    
    print(f"API_SERVER: Cache miss. Synthesizing text: \"{text_request[:50]}...\"")

    try:
        # 1. Get audio chunks from F5TTS backend via our socket client
        # This function now returns List[Optional[np.ndarray]]
        raw_audio_chunks = tts_socket_client.synthesize_text_via_socket(
            text_request, F5TTS_BACKEND_IP, F5TTS_BACKEND_PORT
        )

        if not raw_audio_chunks: # Either no sentences or all failed
            print(f"API_SERVER: No valid audio chunks received from TTS backend for: \"{text_request[:50]}...\"")
            # Return a short silent WAV or an error
            silent_wav = audio_utils.convert_float32_to_wav_bytes(None, API_SAMPLE_RATE)
            return Response(content=silent_wav, media_type="audio/wav", status_code=200) # Or 503 if backend error

        # 2. Mix audio chunks with crossfade
        final_audio_np = audio_utils.mix_audio_chunks_with_crossfade(
            raw_audio_chunks, API_SAMPLE_RATE, API_OVERLAP_MS
        )

        if final_audio_np is None or final_audio_np.size == 0:
            print(f"API_SERVER: Audio mixing resulted in no audio data for: \"{text_request[:50]}...\"")
            silent_wav = audio_utils.convert_float32_to_wav_bytes(None, API_SAMPLE_RATE)
            return Response(content=silent_wav, media_type="audio/wav", status_code=200)

        # 3. Convert final NumPy audio to WAV bytes
        wav_bytes = audio_utils.convert_float32_to_wav_bytes(final_audio_np, API_SAMPLE_RATE)

        # Update cache (simple eviction if full)
        if len(TTS_CACHE) >= CACHE_MAX_SIZE:
            TTS_CACHE.pop(next(iter(TTS_CACHE))) # Remove oldest item (dict order Python 3.7+)
        TTS_CACHE[text_request] = wav_bytes
        
        print(f"API_SERVER: Successfully synthesized audio. Sending {len(wav_bytes)} WAV bytes.")
        # Return as raw bytes with appropriate media type
        return Response(content=wav_bytes, media_type="audio/wav")

    except tts_socket_client.TTSSocketError as e:
        print(f"API_SERVER: ERROR - TTS backend communication error: {e}")
        return Response(content=f"Error: TTS backend service unavailable or failed: {e}", status_code=503, media_type="text/plain")
    except Exception as e:
        print(f"API_SERVER: ERROR - Unexpected error during TTS synthesis: {e}")
        import traceback
        traceback.print_exc() # Log full traceback for unexpected errors
        return Response(content=f"Error: Internal server error during TTS: {e}", status_code=500, media_type="text/plain")


@app.get("/status/")
async def get_status():
    """Checks if the F5TTS backend socket server is reachable."""
    try:
        s = tts_socket_client.connect_to_tts_server(F5TTS_BACKEND_IP, F5TTS_BACKEND_PORT)
        s.close()
        return {"status": "OK", "message": "TTS Backend is reachable."}
    except tts_socket_client.TTSSocketError as e:
        return fastapi.responses.JSONResponse(
            status_code=503,
            content={"status": "ERROR", "message": f"TTS Backend connection failed: {e}"}
        )

if __name__ == "__main__":
    # For development: uvicorn tts_api_server:app --reload --host 0.0.0.0 --port 8000
    # Change port if needed, e.g. 9999 to match previous discussions for Unity
    uvicorn.run(app, host="0.0.0.0", port=8000) 