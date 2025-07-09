// SimpleTTSClient.cs
using System;
using UnityEngine;
using System.Collections;
using System.Text;
using UnityEngine.Networking; // Unity's newer HTTP request system

public class FastAPIClient : MonoBehaviour
{
    [Header("API Server Configuration")]
    public string apiServerURL = "http://127.0.0.1:8000/speak/"; // Full URL to the /speak/ endpoint

    [Header("Audio Playback")]
    public AudioSource audioSource;

    [Header("Debugging")]
    public bool showDebugMessages = true;

    private Coroutine _currentTTSRequest;

    void Start()
    {
        if (audioSource == null)
        {
            Debug.LogError("TTS Client: AudioSource is not assigned!");
            enabled = false; // Disable script if no AudioSource
        }
    }

    /// <summary>
    /// Requests Text-to-Speech for the given text from the API server.
    /// </summary>
    /// <param name="textToSpeak">The text you want to synthesize.</param>
    public void RequestSpeech(string textToSpeak)
    {
        if (string.IsNullOrEmpty(textToSpeak))
        {
            if (showDebugMessages) Debug.LogWarning("TTS Client: Text to speak is empty. Request ignored.");
            return;
        }

        if (_currentTTSRequest != null)
        {
            if (showDebugMessages) Debug.LogWarning("TTS Client: A speech request is already in progress. Stopping the previous one.");
            StopCoroutine(_currentTTSRequest);
            _currentTTSRequest = null;
            // Optionally, also stop the audioSource if it was playing from the previous request
            if (audioSource.isPlaying)
            {
                audioSource.Stop();
            }
        }

        if (showDebugMessages) Debug.Log($"TTS Client: Requesting speech for: \"{textToSpeak.Substring(0, Mathf.Min(textToSpeak.Length, 50))}...\"");
        _currentTTSRequest = StartCoroutine(SendTTSRequest(textToSpeak));
    }

    /// <summary>
    /// Stops any ongoing TTS request and audio playback.
    /// </summary>
    public void StopSpeech()
    {
        if (_currentTTSRequest != null)
        {
            StopCoroutine(_currentTTSRequest);
            _currentTTSRequest = null;
            if (showDebugMessages) Debug.Log("TTS Client: Ongoing TTS request coroutine stopped.");
        }
        if (audioSource != null && audioSource.isPlaying)
        {
            audioSource.Stop();
            if (showDebugMessages) Debug.Log("TTS Client: Audio playback stopped.");
        }
    }


    private IEnumerator SendTTSRequest(string text)
    {
        // FastAPI with `Body(..., embed=True)` expects a JSON object.
        // So, we need to create a JSON string like: {"text_request": "your text here"}
        string jsonPayload = $"{{\"text_request\": \"{EscapeJsonString(text)}\"}}";
        byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonPayload);

        using (UnityWebRequest www = new UnityWebRequest(apiServerURL, UnityWebRequest.kHttpVerbPOST))
        {
            www.uploadHandler = new UploadHandlerRaw(bodyRaw);
            www.downloadHandler = new DownloadHandlerAudioClip(apiServerURL, AudioType.WAV); // Let Unity handle WAV parsing
            // Important: Set content type for POST request with JSON body
            www.SetRequestHeader("Content-Type", "application/json");
            www.SetRequestHeader("Accept", "audio/wav"); // Tell server we prefer WAV

            if (showDebugMessages) Debug.Log($"TTS Client: Sending POST request to {apiServerURL} with JSON: {jsonPayload}");
            yield return www.SendWebRequest();

            _currentTTSRequest = null; // Mark coroutine as finished

            if (www.result == UnityWebRequest.Result.ConnectionError ||
                www.result == UnityWebRequest.Result.ProtocolError ||
                www.result == UnityWebRequest.Result.DataProcessingError)
            {
                Debug.LogError($"TTS Client: Error - {www.error}");
                if (www.downloadHandler != null && !string.IsNullOrEmpty(www.downloadHandler.text))
                {
                    Debug.LogError($"TTS Client: Server error response - {www.downloadHandler.text}");
                }
            }
            else
            {
                if (showDebugMessages) Debug.Log("TTS Client: Audio received successfully.");
                AudioClip receivedClip = DownloadHandlerAudioClip.GetContent(www);

                if (receivedClip != null)
                {
                    if (audioSource.isPlaying)
                    {
                        audioSource.Stop(); // Stop previous clip if any
                    }
                    audioSource.clip = receivedClip;
                    audioSource.Play();
                    if (showDebugMessages) Debug.Log("TTS Client: Playing received audio clip.");
                }
                else
                {
                    Debug.LogError("TTS Client: Error - Failed to get AudioClip from downloaded data.");
                }
            }
        }
    }

    /// <summary>
    /// Escapes special characters in a string to be safely embedded in a JSON string value.
    /// </summary>
    private string EscapeJsonString(string str)
    {
        if (string.IsNullOrEmpty(str)) return "";

        StringBuilder sb = new StringBuilder();
        foreach (char c in str)
        {
            switch (c)
            {
                case '"': sb.Append("\\\""); break;
                case '\\': sb.Append("\\\\"); break;
                case '\b': sb.Append("\\b"); break;
                case '\f': sb.Append("\\f"); break;
                case '\n': sb.Append("\\n"); break;
                case '\r': sb.Append("\\r"); break;
                case '\t': sb.Append("\\t"); break;
                default:
                    if (c < ' ') // Control characters
                    {
                        // Convert to \uXXXX format
                        sb.AppendFormat("\\u{0:x4}", (int)c);
                    }
                    else
                    {
                        sb.Append(c);
                    }
                    break;
            }
        }
        return sb.ToString();
    }

    void OnDestroy()
    {
        StopSpeech(); // Ensure cleanup when the GameObject is destroyed
    }
}