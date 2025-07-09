// --- START OF FILE F5TTSClient.cs ---

using UnityEngine;
using System;
using System.Collections.Generic;
using System.Net.Sockets;
using System.Text;
using System.Threading;

public class F5TTSClient : MonoBehaviour
{
    public string serverIP = "127.0.0.1";
    public int serverPort = 9998;
    public int sampleRate = 24000;
    public int bufferSize = 2048; // Taille du buffer de réception réseau (en bytes)
    public AudioSource audioSource;

    private string textToSend = "";
    private Queue<float> audioQueue = new Queue<float>();
    private AudioClip streamingClip;
    private Thread streamThread;
    private volatile bool stopRequested = false; // volatile car modifié par thread principal, lu par streamThread
    private volatile bool streamEnded = false;   // volatile car modifié par streamThread, lu par thread principal

    private TcpClient client;
    private NetworkStream stream;

    // Pas besoin de silenceBuffer explicite si OnAudioRead remplit de 0f par défaut
    // ou si l'AudioSource s'arrête correctement.
    // Cependant, le garder peut être utile pour un padding délibéré si nécessaire.
    // Si on veut que l'AudioSource s'arrête net, on peut simplifier OnAudioRead.
    // Mais pour l'instant, gardons-le pour voir l'effet avec l'arrêt correct.
    private float silenceDuration = 0.1f; 
    private int silenceSamples;
    private float[] silenceBuffer;


    void Start()
    {
        if (audioSource == null)
        {
            Debug.LogError("AudioSource non assigné à F5TTSClient.");
            enabled = false; // Désactiver le script si l'AudioSource manque
            return;
        }
        // Assurez-vous que l'AudioSource ne boucle pas par lui-même
        audioSource.loop = false;

        silenceSamples = Mathf.CeilToInt(silenceDuration * sampleRate);
        silenceBuffer = new float[silenceSamples];
        // Remplir avec du silence (0f) est déjà fait par défaut pour les float[]
        // for (int i = 0; i < silenceSamples; i++) silenceBuffer[i] = 0f;
    }

    public void TTSRequest(string textRequest)
    {
        if (string.IsNullOrEmpty(textRequest))
        {
            Debug.LogWarning("⚠️ La requête TTS est vide.");
            return;
        }

        // Si un thread est déjà actif, ne pas démarrer un nouveau.
        if (streamThread != null && streamThread.IsAlive)
        {
            Debug.LogWarning("⚠️ Une requête TTS (thread réseau) est déjà en cours. Veuillez attendre ou l'arrêter.");
            return;
        }
        
        // Si l'AudioSource joue encore (potentiellement du silence du précédent stream), l'arrêter.
        if (audioSource.isPlaying)
        {
            audioSource.Stop();
            Debug.Log("AudioSource arrêté avant une nouvelle requête.");
        }

        // Nettoyer la file d'attente des restes d'un précédent stream
        lock (audioQueue)
        {
            audioQueue.Clear();
        }

        textToSend = textRequest;

        // Créer un nouveau clip. La durée (sampleRate * 60) est une estimation max, OK pour le streaming.
        // Le callback OnAudioRead sera appelé par Unity pour remplir les données.
        streamingClip = AudioClip.Create("StreamingAudio", sampleRate * 60, 1, sampleRate, true, OnAudioRead);
        audioSource.clip = streamingClip;

        stopRequested = false;
        streamEnded = false;

        streamThread = new Thread(SendAndReceiveStream)
        {
            IsBackground = true // Important pour que le thread se termine si l'application quitte
        };
        streamThread.Start();

        audioSource.Play(); // Commence à jouer, ce qui déclenchera OnAudioRead
        Debug.Log("AudioSource.Play() appelé pour la nouvelle requête.");
    }

    // Méthode pour arrêter manuellement le TTS en cours
    public void StopTTS()
    {
        Debug.Log("Arrêt manuel du TTS demandé.");
        stopRequested = true; // Signale au thread réseau de s'arrêter

        if (streamThread != null && streamThread.IsAlive)
        {
            if (!streamThread.Join(1000)) // Attendre jusqu'à 1 seconde que le thread se termine
            {
                Debug.LogWarning("⚠️ Le thread de streaming n'a pas pu être joint à temps, tentative d'Abort.");
                streamThread.Abort(); // Forcer l'arrêt si Join échoue (dernier recours)
            }
            streamThread = null;
        }

        if (audioSource != null && audioSource.isPlaying)
        {
            audioSource.Stop();
            Debug.Log("⏹️ AudioSource arrêté manuellement.");
        }

        lock (audioQueue)
        {
            audioQueue.Clear();
        }
        streamEnded = true; // Marquer comme terminé pour que Update() ne tente pas de le re-arrêter
    }


    void Update()
    {
        // Si le stream est marqué comme terminé par le thread réseau
        // ET que l'AudioSource est toujours en train de jouer
        // ET qu'il n'y a plus d'échantillons audio dans la file
        if (streamEnded && audioSource.isPlaying)
        {
            bool isEmpty;
            lock (audioQueue)
            {
                isEmpty = audioQueue.Count == 0;
            }

            if (isEmpty)
            {
                // Optionnel: Attendre un très court instant pour s'assurer que les derniers
                // échantillons dans le buffer interne d'Unity sont joués avant d'arrêter.
                // Peut être géré par la latence naturelle ou une petite attente ici.
                // Souvent, un simple Stop() est suffisant.
                audioSource.Stop();
                Debug.Log("⏹️ Stream terminé et file vide. AudioSource arrêté.");
                // streamEnded reste true jusqu'à la prochaine requête qui le réinitialisera
            }
        }
    }

    void OnDestroy()
    {
        Debug.Log("F5TTSClient OnDestroy: Nettoyage...");
        StopTTS(); // Utiliser la méthode StopTTS pour un nettoyage propre

        // La fermeture des sockets est gérée dans SendAndReceiveStream ou StopTTS
        // Mais au cas où, une double vérification :
        try
        {
            stream?.Close();
            stream?.Dispose(); // Dispose est important pour NetworkStream
            client?.Close(); // Close sur TcpClient dispose aussi le NetworkStream associé
            client?.Dispose(); 
        }
        catch (Exception e)
        {
            Debug.LogWarning("⚠️ Erreur pendant la fermeture des sockets dans OnDestroy: " + e.Message);
        }
        Debug.Log("F5TTSClient OnDestroy: Nettoyage terminé.");
    }

    // Appelé par Unity sur le thread audio lorsque l'AudioClip a besoin de plus de données
    void OnAudioRead(float[] data)
    {
        int count = 0;
        lock (audioQueue)
        {
            for (int i = 0; i < data.Length; i++)
            {
                if (audioQueue.Count > 0)
                {
                    data[i] = audioQueue.Dequeue();
                    count++;
                }
                else
                {
                    // Si la file est vide, remplir le reste du buffer avec du silence (0f)
                    // Si streamEnded est vrai et que la file est vide, l'AudioSource
                    // sera arrêté par Update(), donc ce silence ne jouera pas longtemps.
                    data[i] = 0f; // Remplir de silence
                }
            }
        }
        // if (count > 0) Debug.Log($"OnAudioRead: {count} samples provided. data.Length: {data.Length}");
        // else if (streamEnded) Debug.Log("OnAudioRead: Filling with silence, stream has ended.");
    }

    void SendAndReceiveStream()
    {
        try
        {
            // Utilisation de using pour s'assurer que client et stream sont disposés
            using (client = new TcpClient())
            {
                // Tenter la connexion avec un timeout (par défaut, peut bloquer longtemps)
                // client.Connect(serverIP, serverPort) n'a pas de timeout direct.
                // Une approche plus robuste impliquerait client.BeginConnect / EndConnect avec un ManualResetEvent.
                // Pour la simplicité, on garde la connexion synchrone.
                Debug.Log($"🔌 Tentative de connexion à F5-TTS server: {serverIP}:{serverPort}");
                client.Connect(serverIP, serverPort); // Peut bloquer, ou lancer SocketException si échec immédiat
                
                using (stream = client.GetStream())
                {
                    Debug.Log("🔌 Connecté à F5-TTS server.");

                    byte[] textBytes = Encoding.UTF8.GetBytes(textToSend);
                    stream.Write(textBytes, 0, textBytes.Length);
                    stream.Flush(); // S'assurer que les données sont envoyées
                    Debug.Log("🟢 Texte envoyé au serveur TTS: " + textToSend);

                    byte[] receiveBuffer = new byte[bufferSize]; // Utiliser la variable membre bufferSize

                    while (!stopRequested) // Boucle principale de réception
                    {
                        if (!stream.CanRead || !client.Connected) // Vérifier si le stream est toujours lisible et client connecté
                        {
                            Debug.LogWarning("⚠️ Stream non lisible ou client déconnecté.");
                            break;
                        }
                        
                        // Check DataAvailable to avoid blocking Read if server is slow or sends END signal late
                        // Note: DataAvailable can be 0 even if data will arrive later.
                        // A Read timeout is better.
                        // stream.ReadTimeout = 5000; // 5 secondes, par exemple

                        int bytesRead;
                        try
                        {
                            // Read peut bloquer indéfiniment si pas de ReadTimeout et pas de données
                            // ou lancer IOException si la connexion est fermée/timeout
                            bytesRead = stream.Read(receiveBuffer, 0, receiveBuffer.Length);
                        }
                        catch (System.IO.IOException ex) // ex: timeout, connexion fermée par le serveur
                        {
                            Debug.LogWarning($"⚠️ IOException pendant stream.Read: {ex.Message}. Arrêt de la réception.");
                            break;
                        }


                        if (bytesRead <= 0) // Connexion fermée par le serveur ou fin de stream
                        {
                            Debug.Log("📭 0 bytes lus ou connexion fermée par le serveur. Fin du stream.");
                            streamEnded = true; // Important de le signaler
                            break;
                        }

                        // Debug.Log($"📥 Bytes reçus: {bytesRead}");

                        // Vérifier si c'est un signal "END"
                        // Il est important de vérifier cela *avant* de supposer que ce sont des données audio.
                        // Le signal "END" pourrait être plus court que 4 bytes.
                        string receivedText = Encoding.UTF8.GetString(receiveBuffer, 0, bytesRead).Trim();
                        if (receivedText == "END")
                        {
                            Debug.Log("✅ Signal 'END' de fin de stream reçu du serveur.");
                            streamEnded = true;
                            break; // Sortir de la boucle de réception
                        }

                        // Si ce n'est pas "END", traiter comme des données audio
                        // S'assurer que le nombre de bytes est un multiple de 4 (taille d'un float)
                        if (bytesRead % 4 != 0)
                        {
                            Debug.LogWarning($"⚠️ Données audio mal alignées reçues ({bytesRead} bytes). Ce paquet est ignoré.");
                            continue; // Ignorer ce paquet et attendre le suivant
                        }

                        int sampleCount = bytesRead / 4;
                        float[] samples = new float[sampleCount];
                        Buffer.BlockCopy(receiveBuffer, 0, samples, 0, bytesRead);

                        lock (audioQueue)
                        {
                            foreach (float sample in samples)
                            {
                                audioQueue.Enqueue(sample);
                            }

                            // Debug.Log($"🎶 Samples ajoutés: {sampleCount}, total dans la file: {audioQueue.Count}");

                            // Limiter la taille de la file d'attente pour éviter une consommation excessive de mémoire
                            // si le réseau est beaucoup plus rapide que la lecture audio.
                            // 10 secondes de buffer audio semble raisonnable.
                            int maxQueueSize = sampleRate * 10; 
                            while (audioQueue.Count > maxQueueSize)
                            {
                                audioQueue.Dequeue(); // Retirer les échantillons les plus anciens
                            }
                        }
                    } // Fin de la boucle while(!stopRequested)
                } // stream est disposé ici
            } // client est disposé ici
        }
        catch (SocketException e)
        {
            Debug.LogError($"❌ Erreur Socket dans TTS Receiver: {e.Message} (Code: {e.SocketErrorCode})");
        }
        catch (ThreadAbortException)
        {
            Debug.Log("ℹ️ Thread de streaming TTS interrompu (Abort).");
            // Le thread a été avorté, nettoyage normal.
        }
        catch (Exception e)
        {
            Debug.LogError($"❌ Erreur inattendue dans TTS Receiver: {e.ToString()}");
        }
        finally
        {
            // S'assurer que streamEnded est vrai si la boucle s'est terminée pour une raison quelconque
            // (stopRequested, erreur, fin normale)
            streamEnded = true; 
            
            // Le client et le stream sont fermés par les blocs 'using',
            // mais en cas d'exception avant leur initialisation ou autre cas,
            // une tentative de fermeture ici peut être redondante mais sûre.
            try { stream?.Close(); } catch { /* Ignorer */ }
            try { client?.Close(); } catch { /* Ignorer */ }

            Debug.Log("🔌 Thread de réception TTS terminé. Connexion au serveur fermée.");
        }
    }
}
// --- END OF FILE F5TTSClient.cs ---