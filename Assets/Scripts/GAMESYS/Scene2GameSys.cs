using UnityEngine;
using UnityEngine.UI;
using System.Collections.Generic;
using System;

/// <summary>
/// Main system for scene 2: connects STT → AI → TTS.
/// </summary>
public class Scene2GameSys : MonoBehaviour
{


    [Header("Scene 2 Game System")]
    [Header("Components")]
    [Tooltip("Ollama API client for AI interaction")]
    [SerializeField]
    private AgentAPI agentAPI;
    [Tooltip("F5 TTS client for text-to-speech")]
    [SerializeField]
    private FastAPIClient TTS;
    [Tooltip("Vosk STT result handler for speech-to-text")]
    [SerializeField]
    private VoskResultText voskSTT; 
    [SerializeField]
    private SwitchStudent switchStudent;
    [Space]
    [Header("Settings")]
    [Tooltip("Speed of TTS voice [0.1 - 3.0] (default 1.0)")]
    [Range(0.1f, 3.0f)]
    public float voice_speed = 1.0f; // Speed of TTS voice (default 1.0, can be adjusted)

    [Tooltip("Mute mode to enable keyboard input instead of voice")]
    public bool muteMode = false; // Mute mode to enable keyboard input instead of voice

    [Tooltip("Array of available microphone devices")]
    public List<string> micNames = new List<string>(); // Array of available microphone devices

    [Space]
    [Header("State (debug)")]
    [Tooltip("User/Player voice input (from STT)")]
    public string avatarSText = "";      // User/Player voice input (from STT)
    private bool avatarSTextSent = false; // Used to avoid re-sending same text

    [Tooltip("AI response (to be spoken)")]
    public string agentSText = "";       // AI response (to be spoken)
    private bool agentSTextSent = false;  // Used to avoid re-speaking the same answer

    void Start()
    {
        string defaultMic = Microphone.devices.Length > 0 ? Microphone.devices[0] : "Aucun micro détecté";
        Debug.Log("Micro utilisé : " + defaultMic);

        Log.Instance.WriteLog($"{DateTime.Now:[dd/MM/yy-HH:mm:ss]} : Starting...");
        Debug.Log("Scene2GameSys: Starting...");
        string[] mics = Microphone.devices;
        for (int i = 0; i < mics.Length; i++)
        {
            micNames.Add(mics[i]);
        }



        // Automatically get references if not manually assigned
        if (agentAPI == null) agentAPI = GetComponentInChildren<AgentAPI>();
        if (agentAPI == null)
        {
            Debug.LogError("AgentAPI component not found in children!");
            return;
        }
        if (TTS == null) TTS = GetComponentInChildren<FastAPIClient>();
        if (TTS == null)
        {
            Debug.LogError("F5TTSClient component not found in children!");
            return;
        }
        if (voskSTT == null) voskSTT = GetComponentInChildren<VoskResultText>();
        if (voskSTT == null)
        {
            Debug.LogError("VoskResultText component not found in children!");
            return;
        }
    }

    void Update()
    {
        // Step 1: If we have new speech-to-text input and it hasn't been sent yet
        if (!avatarSTextSent && !string.IsNullOrEmpty(avatarSText))
        {
            // Send text to the AI
            agentAPI.Run(avatarSText);
            //Debug.Log("Avatar says: " + avatarSText);
            // Reset for next message cycle
            avatarSTextSent = true;
        }

        // Step 2: If we got a new AI response (set by AgentAPI) and we haven’t played it yet
        if (!agentSTextSent && !string.IsNullOrEmpty(agentSText))
        {
            // Speak the AI response using TTS
            switchStudent.Switch();
            TTS.RequestSpeech(agentSText);
            //Debug.Log("Agent says: " + agentSText);
            // Mark as sent so we don't repeat
            agentSTextSent = true;

            // Reset for next message cycle
            avatarSText = "";
            avatarSTextSent = false;
        }
    }

    // Called externally by STT script when speech is recognized
    public void AvatarSays(string text)
    {
        avatarSText = text;
        Log.Instance.WriteLog($"{DateTime.Now:[dd/MM/yy-HH:mm:ss]}[Avatar]: {avatarSText}");
        avatarSTextSent = false; // Force processing in Update
    }

    // Called externally by AgentAPI when AI has responded
    public void AgentSays(string text)
    {
        agentSText = text;
        Log.Instance.WriteLog($"{DateTime.Now:[dd/MM/yy-HH:mm:ss]}[Agent]: {agentSText}");
        agentSTextSent = false; // Force speaking in Update
    }
    void OnDestroy()
    {
        if (TTS != null)
        {
            TTS.StopSpeech();
        }
    }
}
