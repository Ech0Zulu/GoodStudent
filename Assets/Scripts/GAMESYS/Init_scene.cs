using UnityEngine;

public class Init_scene : MonoBehaviour
{
    //[SerializeField]
    //private string Ollama_path = ""; //path to ollama dir
    //[SerializeField]
    //private string Ollama_name = ""; //name of ollama model
    //[SerializeField]
    //private string F5TTS_path = ""; //path to f5tts dir

    void Start()
    {
        //-------------------//
        //      Ollama       //
        //-------------------//
        //check ollama server on port 11434
        //activate it if not turned on

        //-------------------//
        //      F5TTS        //
        //-------------------//
        //check f5tts server on port 9998
        //activate if if not turned on
    }

    private void OnApplicationQuit()
    {
        //-------------------//
        //      Ollama       //
        //-------------------//
        //check ollama server on port 11434
        //deactivate it if not turned off

        //-------------------//
        //      F5TTS        //
        //-------------------//
        //check f5tts server on port 9998
        //deactivate if if not turned off
    }
}
