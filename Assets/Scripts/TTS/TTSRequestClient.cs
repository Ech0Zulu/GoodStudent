using UnityEngine;
using System;
using System.Net.Sockets;
using System.Text;
using System.Threading;

public class TTSRequestSender : MonoBehaviour
{
    public string serverIP = "127.0.0.1";
    public int serverPort = 9998;
    public string textToSend = "Some call me nature. Others call me mother nature.";

    private Thread senderThread;
    private bool requestSent = false;

    void Start()
    {
        // Démarre la requête dans un thread indépendant
        senderThread = new Thread(SendTTSRequest);
        senderThread.Start();
    }

    void OnDestroy()
    {
        senderThread?.Abort();
    }

    void SendTTSRequest()
    {
        try
        {
            using (TcpClient client = new TcpClient(serverIP, serverPort))
            using (NetworkStream stream = client.GetStream())
            {
                byte[] textBytes = Encoding.UTF8.GetBytes(textToSend);
                stream.Write(textBytes, 0, textBytes.Length);
                stream.Flush();
                Debug.Log("🟢 Texte envoyé au serveur TTS : " + textToSend);
                requestSent = true;

                // On garde la connexion ouverte, mais le serveur va générer l'audio
                // qui sera lu par un autre client (TTSStreamClient)
                while (client.Connected)
                {
                    Thread.Sleep(1000); // Garder la connexion en vie sans bloquer Unity
                }
            }
        }
        catch (Exception e)
        {
            Debug.LogError("❌ Erreur lors de l'envoi de la requête TTS : " + e.Message);
        }
    }

    public void SendNewText(string newText)
    {
        textToSend = newText;
        if (!senderThread.IsAlive)
        {
            senderThread = new Thread(SendTTSRequest);
            senderThread.Start();
        }
    }
}