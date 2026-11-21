using System.Globalization;
using UnityEngine;

namespace Bicho.Hands
{
    /// <summary>
    /// Traduce las manos en comandos para el bicho.
    ///
    ///   Mano de manejo (derecha por defecto)
    ///     ✋ palma abierta  = acelerador armado. La palma es un joystick: arriba/abajo = avanzar/retroceder,
    ///                         izquierda/derecha = girar. Zona muerta al centro de la imagen.
    ///     ✊ puño           = STOP.   Sin mano = STOP (hombre muerto, a los 0,3 s).
    ///     ☝️ índice         = modo fino (manejo al 40 %).
    ///   Mano auxiliar (izquierda)
    ///     🤏 pinza          = servo 0 (altura de la mano) y servo 1 (posición horizontal).
    ///     ✌️ / 👍           = se mandan como {"cmd":"gesto"} para que el firmware haga lo que quiera (baile, luz…).
    ///   Espacio o el botón rojo = parada de emergencia con traba (otro Espacio la suelta).
    /// </summary>
    public class BichoHandController : MonoBehaviour
    {
        [Header("Fuentes")]
        public HandTrackingReceiver source;
        public BichoLink link;

        [Header("Manejo")]
        public Handedness driveHand = Handedness.Right;
        [Range(0, 0.3f)] public float deadZone = 0.07f;
        [Tooltip("Desplazamiento desde el centro (en fracción de imagen) que da velocidad máxima")]
        [Range(0.1f, 0.5f)] public float fullScale = 0.25f;
        [Range(0.1f, 1f)] public float maxSpeed = 0.8f;
        [Range(0.1f, 1f)] public float fineScale = 0.4f;
        [Tooltip("Suavizado del acelerador (0 = nada, 0.9 = mucho)")]
        [Range(0, 0.95f)] public float smoothing = 0.6f;
        public float lostHandTimeout = 0.3f;
        public float sendHz = 15f;

        [Header("Servos")]
        public bool servosEnabled = true;

        [Header("Bicho real")]
        [Tooltip("Mandar drive/stop/servo al bicho. Parte apagado: mientras el bicho no tenga esos comandos, cada uno vuelve como aviso «comando desconocido» a todas las consolas de bicho·dev. Los gestos se mandan siempre (uno por cambio).")]
        public bool sendMotion = false;
        [Tooltip("Pulgar arriba → luz verde (si), victoria → responder, puño → luz roja (no). Comandos que el bicho vivo ya entiende (fw 0.10+).")]
        public bool gestureLights = true;

        // Estado visible para el HUD
        public float Left { get; private set; }
        public float Right { get; private set; }
        public float Throttle { get; private set; }
        public float Turn { get; private set; }
        public bool Armed { get; private set; }
        public bool EmergencyStop { get; private set; }
        /// <summary>Palma lista pero fuera del centro: no arranca hasta pasar por la zona muerta (evita salir a fondo si la mano entra por un borde).</summary>
        public bool NeedsCenter { get; private set; }
        public Gesture DriveGesture => _stab[(int)driveHand].Stable;
        public Gesture AuxGesture => _stab[1 - (int)driveHand].Stable;
        public int Servo0 { get; private set; } = 90;
        public int Servo1 { get; private set; } = 90;
        public string LastCommand { get; private set; } = "";

        /// <summary>Se dispara cuando cambia un gesto estable (mano, gesto).</summary>
        public event System.Action<Handedness, Gesture> GestureChanged;

        readonly GestureStabilizer[] _stab = { new GestureStabilizer(), new GestureStabilizer() };
        float _sendT, _servoT;
        bool _wasMoving, _engaged;
        int _sentServo0 = -1, _sentServo1 = -1;

        void Update()
        {
            if (Input.GetKeyDown(KeyCode.Space)) ToggleEmergency();

            var frame = source != null ? source.Latest : null;
            bool fresh = source != null && source.SecondsSinceLast < lostHandTimeout;

            for (int s = 0; s < 2; s++)
            {
                var hand = fresh ? frame.Get((Handedness)s) : null;
                var stab = _stab[s];
                if (hand == null) { if (stab.Stable != Gesture.None && stab.Push(Gesture.None)) OnGesture((Handedness)s, Gesture.None); continue; }
                var pose = GestureRecognizer.Classify(hand, stab.Pinching);
                if (stab.Push(pose.Gesture)) OnGesture((Handedness)s, stab.Stable);
            }

            // ---- Manejo ----
            var dh = fresh ? frame.Get(driveHand) : null;
            var dg = DriveGesture;
            float thr = 0, turn = 0;
            Armed = !EmergencyStop && dh != null && (dg == Gesture.OpenPalm || dg == Gesture.Point);
            if (Armed)
            {
                Joystick(dh.PalmCenter, deadZone, fullScale, out thr, out turn);
                if (!_engaged && thr == 0 && turn == 0) _engaged = true;
                if (!_engaged) thr = turn = 0;
                float k = maxSpeed * (dg == Gesture.Point ? fineScale : 1f);
                thr *= k; turn *= k;
            }
            if (!Armed) _engaged = false;
            NeedsCenter = Armed && !_engaged;
            float a = Armed ? smoothing : 0f; // al desarmar se frena de inmediato
            Throttle = Mathf.Lerp(thr, Throttle, a);
            Turn = Mathf.Lerp(turn, Turn, a);
            Mix(Throttle, Turn, out var l, out var r);
            Left = l; Right = r;

            _sendT += Time.unscaledDeltaTime;
            bool moving = Mathf.Abs(Left) > 0.01f || Mathf.Abs(Right) > 0.01f;
            if (_sendT >= 1f / sendHz)
            {
                _sendT = 0;
                if (moving) SendDrive(Left, Right);
                else if (_wasMoving) Send("{\"cmd\":\"stop\"}", critical: true);
                else if (Armed) SendDrive(0, 0); // latido: mantiene vivo el watchdog del firmware
                _wasMoving = moving;
            }

            // ---- Servos con la mano auxiliar ----
            var ah = fresh ? frame.Get(driveHand == Handedness.Right ? Handedness.Left : Handedness.Right) : null;
            _servoT += Time.unscaledDeltaTime;
            if (servosEnabled && !EmergencyStop && ah != null && AuxGesture == Gesture.Pinch)
            {
                var pc = ah.PalmCenter;
                Servo0 = Mathf.RoundToInt(Mathf.Lerp(180, 0, Mathf.InverseLerp(0.2f, 0.8f, pc.y)));
                Servo1 = Mathf.RoundToInt(Mathf.Lerp(0, 180, Mathf.InverseLerp(0.1f, 0.6f, pc.x)));
                if (_servoT >= 1f / sendHz)
                {
                    _servoT = 0;
                    if (Mathf.Abs(Servo0 - _sentServo0) >= 2) { Send($"{{\"cmd\":\"servo\",\"i\":0,\"deg\":{Servo0}}}", true); _sentServo0 = Servo0; }
                    if (Mathf.Abs(Servo1 - _sentServo1) >= 2) { Send($"{{\"cmd\":\"servo\",\"i\":1,\"deg\":{Servo1}}}", true); _sentServo1 = Servo1; }
                }
            }
        }

        void OnGesture(Handedness side, Gesture g)
        {
            GestureChanged?.Invoke(side, g);
            if (g == Gesture.None) return;
            if (side == driveHand && g == Gesture.Fist && _wasMoving) Send("{\"cmd\":\"stop\"}", true);
            string name = GestureName(g);
            Send($"{{\"cmd\":\"gesto\",\"g\":\"{name}\",\"mano\":\"{(side == Handedness.Right ? "der" : "izq")}\"}}", true, motion: false);
            var light = LightFor(g);
            if (gestureLights && light != null) Send($"{{\"cmd\":\"{light}\"}}", true, motion: false);
        }

        public void ToggleEmergency()
        {
            EmergencyStop = !EmergencyStop;
            if (EmergencyStop) { Throttle = Turn = Left = Right = 0; Send("{\"cmd\":\"stop\"}", true); _wasMoving = false; }
        }

        void SendDrive(float l, float r)
            => Send("{\"cmd\":\"drive\",\"l\":" + l.ToString("0.00", CultureInfo.InvariantCulture) +
                    ",\"r\":" + r.ToString("0.00", CultureInfo.InvariantCulture) + "}", critical: false);

        /// <summary>Luz del bicho vivo para cada gesto (comandos si / no / responder de fw 0.10+).</summary>
        public static string LightFor(Gesture g) => g switch
        {
            Gesture.ThumbsUp => "si", Gesture.Victory => "responder", Gesture.Fist => "no", _ => null
        };

        void Send(string json, bool critical, bool motion = true)
        {
            LastCommand = json;
            if (link == null || !link.IsConnected) return;
            if (motion && !sendMotion) return;
            if (critical) link.Enqueue(json); else link.SetDrive(json);
        }

        // ---------- Matemática pura (testeada en Tests/Editor) ----------

        public static string GestureName(Gesture g) => g switch
        {
            Gesture.OpenPalm => "palma", Gesture.Fist => "puno", Gesture.Point => "indice",
            Gesture.Victory => "victoria", Gesture.ThumbsUp => "pulgar_arriba", Gesture.Pinch => "pinza", _ => "ninguno"
        };

        /// <summary>Centro de la palma (0..1, y hacia abajo) → acelerador y giro en -1..1 con zona muerta.</summary>
        public static void Joystick(Vector2 palm, float deadZone, float fullScale, out float throttle, out float turn)
        {
            throttle = Axis(0.5f - palm.y, deadZone, fullScale); // arriba = avanzar
            turn = Axis(palm.x - 0.5f, deadZone, fullScale);     // derecha = girar a la derecha
        }

        public static float Axis(float offset, float dead, float full)
        {
            float a = Mathf.Abs(offset);
            if (a <= dead) return 0f;
            return Mathf.Sign(offset) * Mathf.Clamp01((a - dead) / Mathf.Max(1e-4f, full - dead));
        }

        /// <summary>Mezcla diferencial (tanque). Normaliza para no pasar de ±1 sin perder la proporción.</summary>
        public static void Mix(float throttle, float turn, out float left, out float right)
        {
            left = throttle + turn;
            right = throttle - turn;
            float m = Mathf.Max(1f, Mathf.Max(Mathf.Abs(left), Mathf.Abs(right)));
            left /= m; right /= m;
        }
    }
}
