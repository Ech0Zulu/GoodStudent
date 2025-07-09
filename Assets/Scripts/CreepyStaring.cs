using UnityEngine;

public class CreepyStaring : MonoBehaviour
{
    [SerializeField]
    private Transform targetTransform;
    [SerializeField]
    private Transform headTransform; // The bone/transform you want to rotate

    public Vector3 offset = Vector3.zero; // Optional offset to apply to the target position

    [Header("Head Clamp (Degrees)")]
    [Tooltip("Max rotation around the head's local Y-axis (left/right) from initial forward.")]
    public float headYawLimit = 90f;
    [Tooltip("Max rotation around the head's local X-axis (up/down) from initial forward.")]
    public float headPitchLimit = 60f;
    [Tooltip("Max rotation around the head's local Z-axis (tilt/roll) from initial forward.")]
    public float headRollLimit = 30f; // Often, you might want this to be 0 or very small for heads

    [Header("Rotation Speed")]
    public float rotationSpeed = 5f;

    private Quaternion initialLocalRotation; // Initial rotation of the head relative to its parent
    private Transform headParent; // Parent of the head, used for local space calculations

    void Start()
    {
        // 1. Critical: Check if transforms are assigned.
        if (targetTransform == null)
        {
            Debug.LogError("Target Transform not assigned on " + gameObject.name + " for CreepyStaring script.", this);
            enabled = false; // Disable the script if essential components are missing
            return;
        }
        if (headTransform == null)
        {
            Debug.LogError("Head Transform not assigned on " + gameObject.name + " for CreepyStaring script.", this);
            enabled = false;
            return;
        }

        // 2. Store the initial LOCAL rotation of the head.
        // This is important because the parent (e.g., the NPC body) might rotate,
        // and we want the head's limits to be relative to its own starting pose
        // with respect to its parent.
        initialLocalRotation = headTransform.localRotation;
        headParent = headTransform.parent; // Store for convenience, can be null if head is a root object
    }

    void LateUpdate() // Use LateUpdate for look-at behaviors
    {
        if (targetTransform == null || headTransform == null) return; // Should have been caught in Start, but good for safety

        // --- Calculate Target Rotation in Head's Parent's Local Space ---

        // 3. Get the direction from the head to the target in world space.
        Vector3 worldDirectionToTarget = targetTransform.position - headTransform.position + offset;

        // If the target is exactly at the head's position, we can't get a look rotation.
        if (worldDirectionToTarget == Vector3.zero)
        {
            // Optionally, smoothly return to initial rotation or just do nothing
            // headTransform.localRotation = Quaternion.Slerp(headTransform.localRotation, initialLocalRotation, Time.deltaTime * rotationSpeed);
            return;
        }

        // 4. Determine the "up" vector for the LookRotation.
        // Usually Vector3.up (world up) is fine for heads if they don't roll much based on body.
        // If the body can roll significantly, headParent.up might be more appropriate.
        Vector3 upVector = (headParent != null) ? headParent.up : Vector3.up;

        // 5. Calculate the desired world rotation to look at the target.
        Quaternion targetWorldRotation = Quaternion.LookRotation(worldDirectionToTarget, upVector);

        // 6. Convert this target world rotation into a rotation relative to the head's parent.
        // This is the rotation the head *would need to have in its local space* to look at the target.
        Quaternion targetLocalRotation;
        if (headParent != null)
        {
            targetLocalRotation = Quaternion.Inverse(headParent.rotation) * targetWorldRotation;
        }
        else
        {
            targetLocalRotation = targetWorldRotation; // If no parent, local space is world space
        }

        // --- Clamping ---

        // 7. We want to find the difference between this desired local rotation and our initial local rotation.
        // If R_desiredLocal = R_initialLocal * R_delta, then R_delta = Quaternion.Inverse(R_initialLocal) * R_desiredLocal
        Quaternion deltaRotationFromInitial = Quaternion.Inverse(initialLocalRotation) * targetLocalRotation;

        // 8. Convert this delta rotation to Euler angles.
        // These Euler angles represent the yaw, pitch, and roll *from the initial pose*.
        Vector3 deltaEuler = deltaRotationFromInitial.eulerAngles;

        // 9. Normalize Euler angles to be in the -180 to 180 degree range for easier clamping.
        // This helps avoid issues where 270 degrees is the same as -90 degrees, but Mathf.Clamp wouldn't know.
        float pitch = NormalizeAngle(deltaEuler.x);
        float yaw   = NormalizeAngle(deltaEuler.y);
        float roll  = NormalizeAngle(deltaEuler.z);

        // 10. Clamp these angles.
        // Note: The order of Unity's Euler angles is Z, X, Y for application, but .eulerAngles gives Y (yaw), X (pitch), Z (roll)
        // when thinking about standard "yaw, pitch, roll" terms. Be careful with which component maps to your intuitive sense.
        // For head rotation, typically:
        // Y-axis rotation is Yaw (turning left/right)
        // X-axis rotation is Pitch (looking up/down)
        // Z-axis rotation is Roll (tilting head side-to-side)
        float clampedYaw   = Mathf.Clamp(yaw,   -headYawLimit / 2f,   headYawLimit / 2f);
        float clampedPitch = Mathf.Clamp(pitch, -headPitchLimit / 2f, headPitchLimit / 2f);
        float clampedRoll  = Mathf.Clamp(roll,  -headRollLimit / 2f,  headRollLimit / 2f);

        // 11. Reconstruct the clamped delta rotation from the clamped Euler angles.
        Quaternion clampedDeltaRotation = Quaternion.Euler(clampedPitch, clampedYaw, clampedRoll);

        // 12. Apply this clamped delta rotation to the head's initial local rotation.
        // This gives us the final target local rotation for the head, constrained within limits.
        Quaternion finalLocalRotation = initialLocalRotation * clampedDeltaRotation;

        // 13. Smoothly rotate the head to this final local rotation.
        headTransform.localRotation = Quaternion.Slerp(headTransform.localRotation, finalLocalRotation, Time.deltaTime * rotationSpeed);
    }

    // Helper function to normalize angles to the range [-180, 180]
    private float NormalizeAngle(float angle)
    {
        while (angle > 180f)
            angle -= 360f;
        while (angle < -180f)
            angle += 360f;
        return angle;
    }
}