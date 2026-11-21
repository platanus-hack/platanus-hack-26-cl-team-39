using UnityEngine;

namespace Bicho.Hands
{
    public enum Gesture { None, OpenPalm, Fist, Point, Victory, ThumbsUp, Pinch }

    /// <summary>Lectura instantánea de una mano (sin suavizar).</summary>
    public struct HandPose
    {
        public bool Thumb, Index, Middle, Ring, Pinky;
        /// <summary>Distancia pulgar-índice dividida por el tamaño de la palma (escala-invariante).</summary>
        public float PinchRatio;
        public Gesture Gesture;
        public int ExtendedFingers => (Index ? 1 : 0) + (Middle ? 1 : 0) + (Ring ? 1 : 0) + (Pinky ? 1 : 0);
    }

    /// <summary>
    /// Clasificador geométrico de gestos sobre los 21 puntos. Puro (sin estado), fácil de testear.
    /// Usa los puntos métricos (World) para que no dependa de la distancia a la cámara.
    /// </summary>
    public static class GestureRecognizer
    {
        public const float PinchOn = 0.33f;       // pulgar-índice < 33 % de la palma => pinza
        public const float PinchOff = 0.48f;      // histéresis para soltar

        public static float PalmSize(Vector3[] p) => Mathf.Max(1e-4f, Vector3.Distance(p[LM.Wrist], p[LM.MiddleMcp]));

        public const float MaxBendDeg = 75f;      // flexión mcp→pip→tip bajo esto => estirado (manos reales en movimiento: 40-77°; cerrado: >100°)

        /// <summary>Ángulo (°) entre la falange proximal (mcp→pip) y el resto del dedo (pip→tip). 0 = recto.</summary>
        public static float Bend(Vector3[] p, int mcp, int pip, int tip)
            => Vector3.Angle(p[pip] - p[mcp], p[tip] - p[pip]);

        static bool FingerExtended(Vector3[] p, int mcp, int pip, int tip)
            => Bend(p, mcp, pip, tip) < MaxBendDeg &&
               Vector3.Distance(p[LM.Wrist], p[tip]) > Vector3.Distance(p[LM.Wrist], p[pip]);

        static bool ThumbExtended(Vector3[] p, float palm)
        {
            // Pulgar fuera: su punta se aleja del nudillo del meñique más que la articulación IP,
            // y queda separada del nudillo del índice.
            bool outward = Vector3.Distance(p[LM.ThumbTip], p[LM.PinkyMcp]) > Vector3.Distance(p[LM.ThumbIp], p[LM.PinkyMcp]) * 1.05f;
            bool apart = Vector3.Distance(p[LM.ThumbTip], p[LM.IndexMcp]) > palm * 0.55f;
            return outward && apart;
        }

        /// <param name="wasPinching">estado anterior, para la histéresis de la pinza</param>
        public static HandPose Classify(Hand h, bool wasPinching = false)
        {
            var p = h.World;
            float palm = PalmSize(p);
            var pose = new HandPose
            {
                Index = FingerExtended(p, LM.IndexMcp, LM.IndexPip, LM.IndexTip),
                Middle = FingerExtended(p, LM.MiddleMcp, LM.MiddlePip, LM.MiddleTip),
                Ring = FingerExtended(p, LM.RingMcp, LM.RingPip, LM.RingTip),
                Pinky = FingerExtended(p, LM.PinkyMcp, LM.PinkyPip, LM.PinkyTip),
                Thumb = ThumbExtended(p, palm),
                PinchRatio = Vector3.Distance(p[LM.ThumbTip], p[LM.IndexTip]) / palm,
            };

            bool pinch = pose.PinchRatio < (wasPinching ? PinchOff : PinchOn);
            // En un puño el pulgar suele quedar sobre el índice: solo es pinza si el índice está fuera de la palma.
            bool indexOut = Vector3.Distance(p[LM.IndexTip], p[LM.MiddleMcp]) > palm * 0.55f;
            int n = pose.ExtendedFingers;

            if (pinch && (indexOut || pose.Middle || pose.Ring || pose.Pinky))
                pose.Gesture = Gesture.Pinch;                 // pinza o «OK»
            else if (pose.Index && pose.Middle && pose.Ring)
                pose.Gesture = Gesture.OpenPalm;              // el meñique es opcional: casi nadie lo estira
            else if (n == 0 && pose.Thumb && ThumbPointsUp(h))
                pose.Gesture = Gesture.ThumbsUp;
            else if (n == 0)
                pose.Gesture = Gesture.Fist;
            else if (pose.Index && !pose.Middle && !pose.Ring && !pose.Pinky)
                pose.Gesture = Gesture.Point;
            else if (pose.Index && pose.Middle && !pose.Ring && !pose.Pinky)
                pose.Gesture = Gesture.Victory;
            else
                pose.Gesture = Gesture.None;
            return pose;
        }

        static bool ThumbPointsUp(Hand h)
        {
            // En imagen y crece hacia abajo: la punta del pulgar debe estar claramente sobre los nudillos.
            float palmImg = Vector2.Distance(h.Image[LM.Wrist], h.Image[LM.MiddleMcp]);
            return h.Image[LM.ThumbTip].y < h.Image[LM.IndexMcp].y - palmImg * 0.5f;
        }
    }

    /// <summary>Exige que un gesto se mantenga N cuadros antes de aceptarlo (evita parpadeos).</summary>
    public class GestureStabilizer
    {
        public int framesToConfirm = 3;
        Gesture _candidate = Gesture.None;
        int _streak;
        public Gesture Stable { get; private set; } = Gesture.None;
        public bool Pinching { get; private set; }

        /// <summary>Devuelve true si el gesto estable cambió en este cuadro.</summary>
        public bool Push(Gesture g)
        {
            if (g == _candidate) _streak++;
            else { _candidate = g; _streak = 1; }
            Pinching = Stable == Gesture.Pinch || (g == Gesture.Pinch && _streak >= 1);
            if (_streak >= framesToConfirm && Stable != _candidate)
            {
                Stable = _candidate;
                Pinching = Stable == Gesture.Pinch;
                return true;
            }
            return false;
        }

        public void Reset() { _candidate = Gesture.None; _streak = 0; Stable = Gesture.None; Pinching = false; }
    }
}
