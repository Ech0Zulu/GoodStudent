using System.Collections;
using TMPro;
using UnityEngine;
using UnityEngine.SceneManagement;

public class Scene1GameSys : MonoBehaviour
{

    public bool startGame = false;
    public bool isStarted = false;
    public string sceneToLoad = "Scene2 Learning";
    [SerializeField]
    private TMP_Text timer;
    [SerializeField]
    private GameObject timerPanel;

    void Update()
    {
        if (startGame && !isStarted)
        {
            OnStartButtonPressed();
            startGame = false;
            isStarted = true;
        }
    }

    public void OnStartButtonPressed()
    {
        StartCoroutine(StartDelay());
    }

    IEnumerator StartDelay()
    {
        timerPanel.SetActive(true);
        float countdown = 5f;

        while (countdown > 0f)
        {
            timer.text = Mathf.CeilToInt(countdown).ToString();
            yield return null; // Wait one frame
            countdown -= Time.deltaTime;
        }

        timer.text = "0";

        yield return new WaitForSeconds(0.5f); // small pause before switch
        SceneManager.LoadScene(sceneToLoad);
    }

    public void StartGame()
    {
        startGame = true;
    }
}
