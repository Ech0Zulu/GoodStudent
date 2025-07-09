using System.Collections.Generic;
using UnityEngine;

public class SwitchStudent : MonoBehaviour
{
    [SerializeField]
    private List<GameObject> targetPositions = new List<GameObject>();

    public void Switch()
    {
        transform.position = targetPositions[Random.Range(0,targetPositions.Count)].transform.position;
    }
}
