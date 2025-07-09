using UnityEngine;

public class OrbitMover : MonoBehaviour
{
    [Header("Orbit Settings")]
    public GameObject centerPoint;         // Centre autour duquel on tourne
    public float orbitDistance = 5f;      // Distance à laquelle on tourne
    public float orbitHeight = 0f;       // Hauteur de l'orbite (par rapport au centre)
    public float orbitSpeed = 30f;        // Vitesse de rotation (en degrés/sec)
    public Vector3 orbitAxis = Vector3.up; // Axe de rotation (Y = horizontal)

    private float angle; // angle actuel

    void Update()
    {
        if (centerPoint == null)
            return;
        angle += orbitSpeed * Time.deltaTime;
        angle %= 360f; // Reste entre 0 et 360

        // Calcul de la nouvelle position autour du centre
        Vector3 offset = Quaternion.AngleAxis(angle, orbitAxis.normalized) * Vector3.forward * orbitDistance;
        offset.y = orbitHeight;
        transform.position = centerPoint.transform.position + offset;
    }
}
