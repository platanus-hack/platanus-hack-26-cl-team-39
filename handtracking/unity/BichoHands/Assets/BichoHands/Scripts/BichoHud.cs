using UnityEngine;

namespace Bicho.Hands
{
    /// <summary>Panel de control con IMGUI (cero dependencias): conexión, gestos, motores y parada de emergencia.</summary>
    public class BichoHud : MonoBehaviour
    {
        public BichoHandsApp app;
        string _host, _clave;
        GUIStyle _title, _label, _big, _stop;
        Texture2D _px;

        void Start() { _host = app.link.host; _clave = app.link.clave; }

        void Styles()
        {
            if (_title != null) return;
            _px = new Texture2D(1, 1); _px.SetPixel(0, 0, Color.white); _px.Apply();
            _title = new GUIStyle(GUI.skin.label) { fontSize = 18, fontStyle = FontStyle.Bold };
            _title.normal.textColor = new Color(0.17f, 0.97f, 0.83f);
            _label = new GUIStyle(GUI.skin.label) { fontSize = 13, richText = true };
            _big = new GUIStyle(GUI.skin.label) { fontSize = 26, fontStyle = FontStyle.Bold, alignment = TextAnchor.MiddleCenter, richText = true };
            _stop = new GUIStyle(GUI.skin.button) { fontSize = 20, fontStyle = FontStyle.Bold };
        }

        void Rect(Rect r, Color c) { var o = GUI.color; GUI.color = c; GUI.DrawTexture(r, _px); GUI.color = o; }

        void OnGUI()
        {
            Styles();
            var c = app.controller; var link = app.link; var rx = app.receiver;
            // Escala para pantallas Retina / ventanas grandes: el diseño está pensado para 720 px de alto.
            float k = Mathf.Max(1f, Screen.height / 720f);
            GUI.matrix = Matrix4x4.Scale(new Vector3(k, k, 1));
            float sw = Screen.width / k, sh = Screen.height / k;

            // Guía del joystick: zona muerta en el centro de la imagen
            float dz = c.deadZone, fs = c.fullScale;
            Rect(new Rect(sw * (0.5f - fs), sh * (0.5f - fs), sw * fs * 2, 1), new Color(1, 1, 1, 0.15f));
            Rect(new Rect(sw * (0.5f - fs), sh * (0.5f + fs), sw * fs * 2, 1), new Color(1, 1, 1, 0.15f));
            Rect(new Rect(sw * (0.5f - dz), sh * (0.5f - dz), sw * dz * 2, sh * dz * 2), new Color(0.17f, 0.97f, 0.83f, 0.07f));

            // Panel izquierdo
            Rect(new Rect(10, 10, 330, 340), new Color(0, 0, 0.12f, 0.82f));
            GUILayout.BeginArea(new Rect(22, 18, 306, 330));
            GUILayout.Label("bicho · hand tracking", _title);
            GUILayout.Label($"Manos: {rx.Status}", _label);
            GUILayout.Space(6);
            GUILayout.Label("IP del Pi, o https://<relé> desde otra red:", _label);
            GUILayout.BeginHorizontal();
            _host = GUILayout.TextField(_host, GUILayout.Width(206));
            if (!link.IsConnected) { if (GUILayout.Button("Conectar")) { link.host = _host; link.clave = _clave; app.SaveHost(_host, _clave); link.Connect(); } }
            else if (GUILayout.Button("Desconectar")) link.Disconnect();
            GUILayout.EndHorizontal();
            if (BichoLink.LooksLikeRelay(_host))
            {
                GUILayout.BeginHorizontal();
                GUILayout.Label("Clave del equipo:", _label, GUILayout.Width(110));
                _clave = GUILayout.PasswordField(_clave ?? "", '*', GUILayout.Width(150));
                GUILayout.EndHorizontal();
            }
            GUILayout.Label($"Bicho: {(link.IsConnected ? "<color=#2BF7D4>" : "<color=#FFB040>")}{link.Status}</color>", _label);
            if (link.IsConnected && link.IsRelay)
                GUILayout.Label(!link.BichoOnline ? "<color=#FFB040>el relé no ve al bicho (¿Pi apagado o sin WiFi?)</color>"
                              : !link.CanCommand ? "<color=#FF5050>la clave no sirve: el relé no deja mandar comandos</color>"
                              : "<color=#2BF7D4>bicho en línea por el relé</color>", _label);
            c.gestureLights = GUILayout.Toggle(c.gestureLights, " gestos prenden luces del bicho (pulgar, V, puño)");
            c.sendMotion = GUILayout.Toggle(c.sendMotion, c.sendMotion ? " <b>enviando manejo al bicho</b>" : " enviar manejo al bicho (solo gestos ahora)");
            if (!string.IsNullOrEmpty(link.LastLog)) GUILayout.Label($"<size=11>bicho: {link.LastLog}</size>", _label);
            if (link.Info != null) GUILayout.Label($"fw {link.Info.fw}", _label);
            var t = link.LastTelemetry?.d;
            if (t != null)
                GUILayout.Label($"dist {t.dist_cm:0} cm · inclin. {t.imu?.pitch:0}° · giro {t.imu?.roll:0}° · CPU {t.temp_cpu:0}°C", _label);
            else
                GUILayout.Label(link.IsConnected ? "sin telemetría aún" : "<i>sin robot: maneja el bicho virtual</i>", _label);
            GUILayout.Space(6);
            GUILayout.Label($"Mano {(c.driveHand == Handedness.Right ? "der." : "izq.")} (manejo): <b>{Nice(c.DriveGesture)}</b>", _label);
            GUILayout.Label($"Mano {(c.driveHand == Handedness.Right ? "izq." : "der.")} (servos): <b>{Nice(c.AuxGesture)}</b>  · servos {c.Servo0}° / {c.Servo1}°", _label);
            GUILayout.Label($"<size=11>último: {c.LastCommand}</size>", _label);
            GUILayout.EndArea();

            // Barras de motores
            Bar(new Rect(sw - 120, sh - 230, 40, 200), c.Left, "IZQ");
            Bar(new Rect(sw - 66, sh - 230, 40, 200), c.Right, "DER");

            // Estado grande
            string state = c.EmergencyStop ? "<color=#FF5050>PARADA DE EMERGENCIA</color>"
                         : c.NeedsCenter ? "<color=#FFB040>lleva la palma al centro para arrancar</color>"
                         : c.Armed ? "<color=#2BF7D4>MANEJANDO</color>"
                         : c.DriveGesture == Gesture.Fist ? "<color=#FF5050>STOP</color>"
                         : "<color=#FFFFFF>muestra la palma para manejar</color>";
            GUI.Label(new Rect(0, 14, sw, 40), state, _big);

            // Parada de emergencia
            var o = GUI.backgroundColor;
            GUI.backgroundColor = c.EmergencyStop ? new Color(0.2f, 0.8f, 0.4f) : new Color(1f, 0.2f, 0.2f);
            if (GUI.Button(new Rect(20, sh - 76, 300, 56), c.EmergencyStop ? "SOLTAR (Espacio)" : "STOP (Espacio)", _stop)) c.ToggleEmergency();
            GUI.backgroundColor = o;

            // Ayuda
            GUI.Label(new Rect(340, sh - 76, sw - 500, 70),
                "<size=12>PALMA = manejar (arriba avanza, abajo retrocede, lados giran) · PUÑO = stop · ÍNDICE = modo fino\n" +
                "PINZA con la otra mano = mover servos · VICTORIA / PULGAR = gestos al bicho · sin mano = stop</size>", _label);
        }

        void Bar(Rect r, float v, string label)
        {
            Rect(r, new Color(0, 0, 0.12f, 0.8f));
            float mid = r.y + r.height / 2, h = r.height / 2 * Mathf.Abs(v);
            Rect(new Rect(r.x + 4, v >= 0 ? mid - h : mid, r.width - 8, h), v >= 0 ? new Color(0.17f, 0.97f, 0.83f) : new Color(1f, 0.55f, 0.2f));
            Rect(new Rect(r.x, mid, r.width, 1), Color.white);
            GUI.Label(new Rect(r.x - 4, r.yMax + 2, r.width + 8, 20), $"{label} {v:+0.00;-0.00}", _label);
        }

        static string Nice(Gesture g) => g switch
        {
            Gesture.OpenPalm => "palma", Gesture.Fist => "puño", Gesture.Point => "índice",
            Gesture.Victory => "victoria", Gesture.ThumbsUp => "pulgar", Gesture.Pinch => "pinza", _ => "—"
        };
    }
}
