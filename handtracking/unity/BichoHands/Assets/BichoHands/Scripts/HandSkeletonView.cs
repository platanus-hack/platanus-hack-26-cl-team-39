using UnityEngine;

namespace Bicho.Hands
{
    /// <summary>Dibuja las dos manos (21 esferas + huesos) como un holograma frente a la cámara.</summary>
    public class HandSkeletonView : MonoBehaviour
    {
        public HandTrackingReceiver source;
        public BichoHandController controller;
        public Camera cam;
        public float distance = 1.2f;
        public float depthScale = 0.6f;

        static readonly Color Teal = new Color(0.17f, 0.97f, 0.83f);
        static readonly Color Amber = new Color(1f, 0.72f, 0.2f);
        static readonly Color Red = new Color(1f, 0.3f, 0.3f);

        class Rig { public GameObject root; public Transform[] joints; public LineRenderer[] bones; public Material mat; }
        readonly Rig[] _rigs = new Rig[2];

        void Start()
        {
            if (cam == null) cam = Camera.main;
            var shader = Shader.Find("Sprites/Default") ?? Shader.Find("Unlit/Color");
            for (int s = 0; s < 2; s++)
            {
                var rig = new Rig { root = new GameObject(s == 0 ? "Mano izq." : "Mano der."), joints = new Transform[LM.Count], bones = new LineRenderer[LM.Bones.Length / 2] };
                rig.root.transform.SetParent(transform, false);
                rig.mat = new Material(shader);
                for (int i = 0; i < LM.Count; i++)
                {
                    var j = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                    Destroy(j.GetComponent<Collider>());
                    j.name = "p" + i;
                    j.transform.SetParent(rig.root.transform, false);
                    j.transform.localScale = Vector3.one * (i % 4 == 0 && i > 0 ? 0.022f : 0.016f);
                    j.GetComponent<Renderer>().sharedMaterial = rig.mat;
                    rig.joints[i] = j.transform;
                }
                for (int b = 0; b < rig.bones.Length; b++)
                {
                    var go = new GameObject("hueso" + b);
                    go.transform.SetParent(rig.root.transform, false);
                    var lr = go.AddComponent<LineRenderer>();
                    lr.positionCount = 2; lr.widthMultiplier = 0.007f; lr.sharedMaterial = rig.mat;
                    lr.numCapVertices = 2;
                    rig.bones[b] = lr;
                }
                rig.root.SetActive(false);
                _rigs[s] = rig;
            }
        }

        void LateUpdate()
        {
            var f = source != null && source.SecondsSinceLast < 0.5f ? source.Latest : null;
            for (int s = 0; s < 2; s++)
            {
                var hand = f?.Get((Handedness)s);
                var rig = _rigs[s];
                if (rig == null) continue;
                rig.root.SetActive(hand != null);
                if (hand == null) continue;

                for (int i = 0; i < LM.Count; i++)
                {
                    var p = hand.Image[i];
                    rig.joints[i].position = cam.ViewportToWorldPoint(new Vector3(p.x, 1f - p.y, distance + p.z * depthScale));
                }
                for (int b = 0; b < rig.bones.Length; b++)
                {
                    rig.bones[b].SetPosition(0, rig.joints[LM.Bones[b * 2]].position);
                    rig.bones[b].SetPosition(1, rig.joints[LM.Bones[b * 2 + 1]].position);
                }
                rig.mat.color = ColorFor((Handedness)s);
            }
        }

        Color ColorFor(Handedness side)
        {
            if (controller == null) return Teal;
            if (side == controller.driveHand)
                return controller.EmergencyStop || controller.DriveGesture == Gesture.Fist ? Red : controller.Armed ? Teal : Color.white;
            return controller.AuxGesture == Gesture.Pinch ? Amber : Color.white;
        }
    }
}
