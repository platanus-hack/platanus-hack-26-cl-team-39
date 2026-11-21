using UnityEngine;

namespace Bicho.Hands
{
    /// <summary>
    /// Gemelo digital simple del bicho (chasis 4WD con tracción diferencial). Se mueve con los mismos
    /// l/r que se mandan al robot real, así la demo funciona aunque el bicho esté desconectado.
    /// </summary>
    public class VirtualBicho : MonoBehaviour
    {
        public BichoHandController controller;
        public float maxSpeed = 0.6f;     // m/s a l=r=1
        public float trackWidth = 0.16f;  // m entre ruedas izq./der.
        public float arena = 1.6f;        // medio lado de la pista

        Transform[] _wheels;
        Transform _servoHead;

        void Start()
        {
            var body = Box("Cuerpo", new Vector3(0, 0.07f, 0), new Vector3(0.14f, 0.05f, 0.22f), new Color(0.12f, 0.13f, 0.2f));
            Box("Piso 2", new Vector3(0, 0.115f, 0), new Vector3(0.13f, 0.006f, 0.2f), new Color(0.75f, 0.9f, 1f, 1f));
            Box("Caja Pi", new Vector3(0, 0.16f, -0.03f), new Vector3(0.09f, 0.08f, 0.1f), new Color(0.72f, 0.58f, 0.4f));
            _servoHead = Box("Cabeza (servo)", new Vector3(0, 0.23f, 0.04f), new Vector3(0.06f, 0.04f, 0.04f), new Color(0.17f, 0.97f, 0.83f)).transform;
            _wheels = new Transform[4];
            int k = 0;
            foreach (var z in new[] { 0.07f, -0.07f })
                foreach (var x in new[] { -0.09f, 0.09f })
                {
                    var w = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                    Destroy(w.GetComponent<Collider>());
                    w.name = "Rueda";
                    w.transform.SetParent(transform, false);
                    w.transform.localPosition = new Vector3(x, 0.033f, z);
                    w.transform.localRotation = Quaternion.Euler(0, 0, 90);
                    w.transform.localScale = new Vector3(0.066f, 0.013f, 0.066f);
                    w.GetComponent<Renderer>().material.color = new Color(1f, 0.82f, 0.1f);
                    _wheels[k++] = w.transform;
                }
            body.name = "Cuerpo";
        }

        GameObject Box(string name, Vector3 pos, Vector3 size, Color c)
        {
            var g = GameObject.CreatePrimitive(PrimitiveType.Cube);
            Destroy(g.GetComponent<Collider>());
            g.name = name;
            g.transform.SetParent(transform, false);
            g.transform.localPosition = pos;
            g.transform.localScale = size;
            g.GetComponent<Renderer>().material.color = c;
            return g;
        }

        void Update()
        {
            if (controller == null) return;
            float vl = controller.Left * maxSpeed, vr = controller.Right * maxSpeed;
            float v = (vl + vr) * 0.5f;
            float w = (vl - vr) / trackWidth; // rad/s, positivo = gira a la derecha (horario visto desde arriba)
            float dt = Time.deltaTime;
            transform.Rotate(0, w * Mathf.Rad2Deg * dt * 0.35f, 0, Space.World);
            transform.position += transform.forward * v * dt;
            var p = transform.position;
            p.x = Mathf.Clamp(p.x, -arena, arena); p.z = Mathf.Clamp(p.z, -arena, arena);
            transform.position = p;

            for (int i = 0; i < _wheels.Length; i++)
            {
                float side = (i % 2 == 0) ? vl : vr;
                _wheels[i].Rotate(0, side / 0.033f * Mathf.Rad2Deg * dt, 0, Space.Self);
            }
            if (_servoHead != null)
                _servoHead.localRotation = Quaternion.Euler(Mathf.Lerp(-40, 40, controller.Servo0 / 180f), Mathf.Lerp(-70, 70, controller.Servo1 / 180f), 0);
        }
    }
}
