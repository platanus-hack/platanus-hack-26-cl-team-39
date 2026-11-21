using UnityEngine;

namespace Bicho.Hands
{
    /// <summary>
    /// Arma toda la app en tiempo de ejecución: no hace falta configurar escena.
    /// Abre el proyecto, abre cualquier escena (o una vacía) y aprieta Play.
    /// Para desactivarlo en una escena propia, agrega un objeto con BichoHandsApp ya configurado.
    /// </summary>
    public class BichoHandsApp : MonoBehaviour
    {
        public HandTrackingReceiver receiver;
        public BichoLink link;
        public BichoHandController controller;

        const string PrefHost = "bicho.host";

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Bootstrap()
        {
            if (FindObjectOfType<BichoHandsApp>() != null) return;
            var go = new GameObject("Bicho Hands");
            go.AddComponent<BichoHandsApp>().Build();
        }

        void Build()
        {
            Application.targetFrameRate = 60;
            Application.runInBackground = true; // que no se pare el control si se pierde el foco

            receiver = gameObject.AddComponent<HandTrackingReceiver>();
            link = gameObject.AddComponent<BichoLink>();
            link.host = PlayerPrefs.GetString(PrefHost, link.host);
            controller = gameObject.AddComponent<BichoHandController>();
            controller.source = receiver;
            controller.link = link;

            // Cámara mirando la pista desde atrás-arriba
            var cam = Camera.main;
            if (cam == null)
            {
                var cgo = new GameObject("Main Camera") { tag = "MainCamera" };
                cam = cgo.AddComponent<Camera>();
            }
            cam.transform.position = new Vector3(0, 1.35f, -2.1f);
            cam.transform.rotation = Quaternion.Euler(30, 0, 0);
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.02f, 0.02f, 0.08f);
            cam.fieldOfView = 55;
            cam.nearClipPlane = 0.05f;

            if (FindObjectOfType<Light>() == null)
            {
                var l = new GameObject("Sol").AddComponent<Light>();
                l.type = LightType.Directional;
                l.intensity = 1.1f;
                l.transform.rotation = Quaternion.Euler(50, -30, 0);
            }
            RenderSettings.ambientLight = new Color(0.35f, 0.38f, 0.45f);

            // Pista
            var floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
            floor.name = "Pista";
            floor.transform.localScale = Vector3.one * 0.34f;
            floor.GetComponent<Renderer>().material.color = new Color(0.08f, 0.09f, 0.16f);
            Grid(1.6f, 0.2f);

            var bicho = new GameObject("Bicho virtual").AddComponent<VirtualBicho>();
            bicho.controller = controller;

            var skel = new GameObject("Manos").AddComponent<HandSkeletonView>();
            skel.source = receiver; skel.controller = controller; skel.cam = cam;

            var hud = gameObject.AddComponent<BichoHud>();
            hud.app = this;
        }

        static void Grid(float half, float step)
        {
            var mat = new Material(Shader.Find("Sprites/Default")) { color = new Color(0.17f, 0.97f, 0.83f, 0.18f) };
            var root = new GameObject("Grilla");
            for (float v = -half; v <= half + 1e-3f; v += step)
            {
                Line(root, mat, new Vector3(v, 0.002f, -half), new Vector3(v, 0.002f, half));
                Line(root, mat, new Vector3(-half, 0.002f, v), new Vector3(half, 0.002f, v));
            }
        }

        static void Line(GameObject parent, Material m, Vector3 a, Vector3 b)
        {
            var lr = new GameObject("l").AddComponent<LineRenderer>();
            lr.transform.SetParent(parent.transform, false);
            lr.sharedMaterial = m; lr.widthMultiplier = 0.004f; lr.positionCount = 2;
            lr.SetPosition(0, a); lr.SetPosition(1, b);
        }

        public void SaveHost(string host) { PlayerPrefs.SetString(PrefHost, host); PlayerPrefs.Save(); }
    }
}
