# test_client.py
import requests # To make HTTP requests
import wave
import io

API_SERVER_URL = "http://127.0.0.1:8000" # URL of your FastAPI server

def send_text_to_api(text: str, endpoint: str = "/speak/") -> bytes:
    """Sends text to the FastAPI TTS API and returns the audio bytes."""
    url = API_SERVER_URL.rstrip('/') + '/' + endpoint.lstrip('/')
    print(f"TEST_CLIENT: Sending text to API: {url}")
    try:
        # FastAPI expects JSON body if using Pydantic models, 
        # but for a single string, `data` or `json` can work.
        # Here, we use `json` to match `fastapi.Body(..., embed=True)`.
        response = requests.post(url, json={"text_request": text}) # Send as JSON object
        
        response.raise_for_status() # Raises an HTTPError for bad responses (4XX or 5XX)
        
        if response.headers.get('content-type') == 'audio/wav':
            print("TEST_CLIENT: Received WAV audio successfully.")
            return response.content
        else:
            print(f"TEST_CLIENT: Received non-WAV response: {response.text}")
            return response.content # Or handle as error
            
    except requests.exceptions.RequestException as e:
        print(f"TEST_CLIENT: ERROR - Request to API failed: {e}")
        return b"" # Return empty bytes on error

def save_audio_bytes(audio_bytes: bytes, path: str = "output_test.wav"):
    """Saves a complete WAV file (in bytes) to disk."""
    if not audio_bytes:
        print("TEST_CLIENT: No audio bytes to save.")
        return
    try:
        with open(path, 'wb') as f:
            f.write(audio_bytes)
        print(f"TEST_CLIENT: Audio saved to {path}")
    except Exception as e:
        print(f"TEST_CLIENT: ERROR - Could not save audio file: {e}")

    except Exception as e:
        print(f"TEST_CLIENT: ERROR - Could not save audio file: {e}")

def check_api_status(endpoint: str = "/status/"):
    url = API_SERVER_URL.rstrip('/') + '/' + endpoint.lstrip('/')
    print(f"TEST_CLIENT: Checking API status at {url}")
    try:
        response = requests.get(url)
        response.raise_for_status()
        print(f"TEST_CLIENT: API Status: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"TEST_CLIENT: ERROR - Failed to get API status: {e}")


if __name__ == "__main__":
    check_api_status()
    
    sample_text = "Hello world. This is a test of the FastAPI TTS system."
    # sample_text = "Testing one sentence."
    # sample_text = "First sentence. Second sentence for crossfade. And a third one."

    audio_data = send_text_to_api(sample_text)
    if audio_data:
        save_audio_bytes(audio_data, "test_api_output.wav")

    # Test with empty text
    print("\nTEST_CLIENT: Testing with empty text...")
    audio_data_empty = send_text_to_api("")
    if audio_data_empty:
         # Expecting error or silent wav
        content_type = requests.head(API_SERVER_URL.rstrip('/') + "/speak/").headers.get('content-type', 'unknown')
        if b"Error" in audio_data_empty and content_type != 'audio/wav':
             print(f"TEST_CLIENT: Received expected error for empty text: {audio_data_empty.decode()}")
        else:
            save_audio_bytes(audio_data_empty, "test_api_output_empty.wav")

    # Test with text that might cause backend failure (if backend is sensitive)
    # print("\nTEST_CLIENT: Testing with potentially problematic text...")
    # audio_data_fail = send_text_to_api("...") 
    # if audio_data_fail:
    #     save_audio_bytes(audio_data_fail, "test_api_output_fail.wav")