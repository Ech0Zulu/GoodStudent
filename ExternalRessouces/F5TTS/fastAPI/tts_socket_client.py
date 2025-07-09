# tts_socket_client.py
import socket
import re
import numpy as np
import time # For potential delays or timeouts not covered by socket.timeout
from typing import List, Optional

# Configuration for the F5TTS Backend connection
SOCKET_TIMEOUT = 10.0  # Timeout for individual socket operations with F5TTS backend
RECEIVE_BUFFER_SIZE = 8192
FLOAT_SIZE = np.dtype(np.float32).itemsize

class TTSSocketError(Exception):
    """Custom exception for TTS socket client errors."""
    pass

def split_text_into_sentences(text: str) -> List[str]:
    """Splits text into sentences based on common punctuation."""
    if not text or not text.strip():
        return []
    # Split by '.', '?', '!' followed by whitespace, keeping punctuation.
    sentences = re.split(r'(?<=[.?!])\s+', text.strip())
    return [s for s in sentences if s.strip()] # Filter out empty strings from split

def connect_to_tts_server(ip: str, port: int) -> socket.socket:
    """Establishes a connection to the TTS backend server."""
    print(f"SOCKET_CLIENT: Attempting to connect to TTS Backend at {ip}:{port}...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(SOCKET_TIMEOUT)
        s.connect((ip, port))
        print(f"SOCKET_CLIENT: Successfully connected to TTS Backend.")
        return s
    except socket.timeout:
        raise TTSSocketError(f"Connection to TTS Backend {ip}:{port} timed out.")
    except ConnectionRefusedError:
        raise TTSSocketError(f"Connection to TTS Backend {ip}:{port} refused.")
    except Exception as e:
        raise TTSSocketError(f"Failed to connect to TTS Backend {ip}:{port}: {e}")

def send_text_and_receive_audio_chunk(sentence: str, tts_socket: socket.socket) -> Optional[np.ndarray]:
    """
    Sends a single sentence to the connected TTS backend and receives the audio chunk.
    Returns a NumPy array of float32 samples, or None on failure/no audio.
    """
    print(f"SOCKET_CLIENT: Sending sentence to TTS Backend: \"{sentence[:50]}...\"")
    audio_data_bytes = bytearray()
    try:
        tts_socket.sendall(sentence.encode("utf-8"))
        
        print(f"SOCKET_CLIENT: Receiving audio data for sentence...")
        while True:
            try:
                data = tts_socket.recv(RECEIVE_BUFFER_SIZE)
            except socket.timeout:
                print(f"SOCKET_CLIENT: WARN - Recv timed out waiting for audio data for \"{sentence[:20]}...\". Assuming end of chunk.")
                break # Assume end of data for this chunk if server just stops sending

            if b"END" in data: # Assuming backend sends an "END" marker
                end_idx = data.find(b"END")
                audio_data_bytes.extend(data[:end_idx])
                # print(f"SOCKET_CLIENT: DEBUG - Received END marker.")
                break
            if not data: # Connection closed by server
                # print(f"SOCKET_CLIENT: DEBUG - Connection closed by TTS backend.")
                break
            audio_data_bytes.extend(data)
        
        if not audio_data_bytes:
            print(f"SOCKET_CLIENT: WARN - No audio data bytes received for sentence: \"{sentence[:50]}...\"")
            return None

        if len(audio_data_bytes) % FLOAT_SIZE != 0:
            original_len = len(audio_data_bytes)
            valid_len = (len(audio_data_bytes) // FLOAT_SIZE) * FLOAT_SIZE
            print(f"SOCKET_CLIENT: WARN - Received data length ({original_len}) not multiple of {FLOAT_SIZE}. Truncating to {valid_len}.")
            if valid_len == 0:
                return None
            audio_data_bytes = audio_data_bytes[:valid_len]
        
        audio_array = np.frombuffer(audio_data_bytes, dtype=np.float32)
        print(f"SOCKET_CLIENT: Received {audio_array.size} audio samples for sentence.")
        return audio_array

    except socket.timeout: # Timeout on sendall
        print(f"SOCKET_CLIENT: ERROR - Sendall timed out for sentence: \"{sentence[:50]}...\"")
        raise TTSSocketError(f"Sendall timed out for sentence: \"{sentence[:50]}...\"")
    except Exception as e:
        print(f"SOCKET_CLIENT: ERROR - Exception during send/receive for \"{sentence[:50]}...\": {e}")
        # We might not want to raise TTSSocketError here if we want to try other sentences.
        # For now, let's return None to indicate failure for this chunk.
        return None


def synthesize_text_via_socket(text: str, tts_backend_ip: str, tts_backend_port: int) -> List[Optional[np.ndarray]]:
    """
    Connects to the TTS backend, splits text into sentences, and fetches audio for each.
    Returns a list of NumPy arrays (float32 samples), one for each sentence.
    An item in the list can be None if fetching for that sentence failed.
    Manages a single connection for all sentences in the text.
    """
    sentences = split_text_into_sentences(text)
    if not sentences:
        print("SOCKET_CLIENT: No sentences to synthesize.")
        return []

    all_audio_chunks: List[Optional[np.ndarray]] = []
    tts_socket: Optional[socket.socket] = None

    try:
        tts_socket = connect_to_tts_server(tts_backend_ip, tts_backend_port)
        for i, sentence in enumerate(sentences):
            print(f"SOCKET_CLIENT: Processing sentence {i+1}/{len(sentences)}")
            # Optional: Add a small delay if the backend needs it between requests on the same socket
            # time.sleep(0.05) 
            chunk = send_text_and_receive_audio_chunk(sentence, tts_socket)
            all_audio_chunks.append(chunk)
        return all_audio_chunks
    except TTSSocketError as e: # Catch connection errors
        print(f"SOCKET_CLIENT: ERROR - TTSSocketError during synthesis: {e}")
        # If connection failed, all subsequent chunks would fail.
        # We might return a list of Nones or just an empty list.
        # For now, let the partially filled list (if any) or empty list be returned.
        # Or re-raise to signal API server of total failure. For now, let's re-raise.
        raise
    finally:
        if tts_socket:
            print("SOCKET_CLIENT: Closing connection to TTS Backend.")
            try:
                tts_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass # Socket might already be closed
            tts_socket.close()