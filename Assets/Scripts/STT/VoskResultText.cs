using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class VoskResultText : MonoBehaviour 
{
    [SerializeField]
    private VoskSpeechToText VoskSpeechToText;
    [SerializeField]
    private Scene2GameSys GameSys;
    [SerializeField]
    private TMP_Text outputText;

    void Awake()
    {
        VoskSpeechToText.OnTranscriptionResult += OnTranscriptionResult;
    }

    private void OnTranscriptionResult(string obj)
    {
        var result = new RecognitionResult(obj);
        if (result.Phrases[0].Text.Length > 1)
        {
            outputText.text = result.Phrases[0].Text;
            Debug.Log("Vosk Result: " + result.Phrases[0].Text);
            GameSys.AvatarSays(result.Phrases[0].Text);
        }
    }
}
