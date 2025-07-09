using UnityEngine;
using System;
using System.Net.Sockets;
using System.Threading;
using System.Collections.Generic;

public class TTSStreamClient : MonoBehaviour
{
    public string serverIP = "127.0.0.1";
    public int serverPort = 9998;
    public int sampleRate = 24000;
    public int bufferSize = 2048; // Nombre de samples par chunk
    public AudioSource audioSource;
    private Queue<float> audioQueue = new Queue<float>();
    private AudioClip streamingClip;
    private int position = 0;
    private bool isPlaying = false;
    private Thread receiverThread;
    private bool stopRequested = false;

    void Start()
    {
        streamingClip = AudioClip.Create("StreamingAudio", sampleRate * 10, 1, sampleRate, true, OnAudioRead);
        audioSource.clip = streamingClip;

        receiverThread = new Thread(AudioReceiver);
        receiverThread.Start();

        audioSource.Play();
        isPlaying = true;
    }

    void OnDestroy()
    {
        stopRequested = true;
        receiverThread?.Join();
    }

    void OnAudioRead(float[] data)
    {
        lock (audioQueue)
        {
            for (int i = 0; i < data.Length; i++)
            {
                if (audioQueue.Count > 0)
                {
                    data[i] = audioQueue.Dequeue();
                }
                else
                {
                    data[i] = 0f;
                }
            }
        }
    }

    void AudioReceiver()
    {
        try
        {
            using (TcpClient client = new TcpClient(serverIP, serverPort))
            using (NetworkStream stream = client.GetStream())
            {
                Debug.Log("🔌 Connexion au serveur F5-TTS ");
                byte[] buffer = new byte[bufferSize * 4]; // float32 = 4 bytes

                while (!stopRequested)
                {
                    int bytesRead = stream.Read(buffer, 0, buffer.Length);
                    if (bytesRead <= 0)
                    {
                        Debug.LogWarning("📭 Aucun octet lu, fermeture de la connexion.");
                        break;
                    }

                    Debug.Log($"📥 Octets reçus : {bytesRead}");

                    if (bytesRead % 4 != 0)
                    {
                        Debug.LogWarning("⚠️ Données mal alignées (pas multiple de 4), ignorées.");
                        continue;
                    }

                    int sampleCount = bytesRead / 4;
                    float[] samples = new float[sampleCount];
                    Buffer.BlockCopy(buffer, 0, samples, 0, bytesRead);

                    lock (audioQueue)
                    {
                        foreach (float sample in samples)
                            audioQueue.Enqueue(sample);

                        Debug.Log($"🎶 Échantillons ajoutés au buffer : {sampleCount}, total : {audioQueue.Count}");

                        while (audioQueue.Count > sampleRate * 5)
                            audioQueue.Dequeue();
                    }
                }
            }
        }
        catch (Exception e)
        {
            Debug.LogError("❌ Erreur TTS Receiver : " + e.Message);
        }
    }
}
