//add all dependencies
using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;
using TMPro;

public class AgentAPI : MonoBehaviour
{
    // Server information for connecting to the local AI model
    public string url = "http://localhost:11434/api/chat";
    public string model = "gemma3:4b";
    public string role = "user";

    // Context sent with the prompt to define AI behavior and tone
    public string context = "You are a student in engineering scholl in computer science named Melvyn, your goal is to learn from users.\n" +
                            "Your responses should be short and concise.\n" +
                            "Ask question, be curious to test the knowledge of the user, and help him explain himself by using question or hints\n" +
                            "Remember to keep the conversation flowing naturally with the following historic :";

    // Chat history string
    public string historic = "";

    // UI element to display the response
    public TMP_Text outputText;
    public Scene2GameSys sceneSys;

    // Serializable classes for JSON payload and response structure
    [Serializable]
    public class Message { public string role; public string content; }

    [Serializable]
    public class Payload { public string model; public List<Message> messages; }

    [Serializable]
    public class ResponseMessage { public string role; public string content; }

    [Serializable]
    public class ResponseData
    {
        public string model;
        public string created_at;
        public ResponseMessage message;
        public bool done;
    }
    void Start()
    {
        if (sceneSys == null) sceneSys = GetComponentInParent<Scene2GameSys>();
    }
    // Public function to run the AI request
    public void Run(string message)
    {
        historic += $"user : {message} \n";
        Debug.Log("📡 Sending request to Ollama with message: " + message);

        // ⚠️ Typo fix: should be `historic` instead of `historique`
        StartCoroutine(SendRequest(context + historic + ") \n now answer the following message :" + message));
    }

    // Coroutine that sends the request and handles the response
    IEnumerator SendRequest(string message)
    {
        string allresponse = "";

        // Create the payload to send
        Payload payload = new Payload
        {
            model = model,
            messages = new List<Message> { new Message { role = role, content = message } }
        };

        // Convert payload to JSON
        string jsonData = JsonUtility.ToJson(payload);

        // Send POST request
        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(jsonData);
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");

            yield return request.SendWebRequest();

            // If request is successful
            if (request.result == UnityWebRequest.Result.Success)
            {
                // Parse the line-by-line streamed response
                string[] lines = request.downloadHandler.text.Split(new[] { '\n' }, StringSplitOptions.RemoveEmptyEntries);
                foreach (string line in lines)
                {
                    try
                    {
                        var tempresponseData = JsonUtility.FromJson<ResponseData>(line);
                        if (tempresponseData.message != null && !string.IsNullOrEmpty(tempresponseData.message.content))
                        {
                            allresponse += tempresponseData.message.content;
                        }
                    }
                    catch (Exception e)
                    {
                        Debug.LogError($"❌ Failed to parse line: {line}\n{e}");
                    }
                }

                historic += $"gemma : {allresponse} \n";
                outputText.text = $"gemma : {allresponse} \n";
                sceneSys.AgentSays(allresponse);
                Debug.Log("✅ Response received: " + allresponse);
            }
            else
            {
                Debug.LogError($"❌ Error: {request.responseCode}");
                Debug.LogError(request.downloadHandler.text);
            }
        }
    }
}
