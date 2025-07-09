using System;
using System.IO;
using UnityEngine;

public class Log : MonoBehaviour
{
    public static Log Instance { get; private set; }
    [SerializeField]
    private string fileName = "C:\\Users\\PVR_24_05\\Desktop\\GoodStudent\\Assets\\Logs\\log.txt";
    private string path = "";
    private string content = "";
        void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }
        Instance = this;
        DontDestroyOnLoad(gameObject);

        path = Path.Combine(Application.persistentDataPath, fileName);
        File.WriteAllText(path, string.Empty);
        WriteLog($"{DateTime.Now:[dd/MM/yy-HH:mm:ss]} : Starting...");
    }

    public void WriteLog(string log)
    {
        content = $"{log}\n";
        try
        {
            File.AppendAllText(path, content);
        }
        catch (Exception e)
        {
            Debug.LogError("Erreur lors de l’écriture dans le log : " + e.Message);
        }

        content = string.Empty;
    }
    
    void OnDestroy()
    {
        WriteLog($"{DateTime.Now:[dd/MM/yy-HH:mm:ss]} : Stopping...");
    }
}
