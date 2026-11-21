using System;
using UnityEngine;

namespace Bicho.Hands
{
    /// <summary>Índices de los 21 puntos de MediaPipe.</summary>
    public static class LM
    {
        public const int Wrist = 0;
        public const int ThumbCmc = 1, ThumbMcp = 2, ThumbIp = 3, ThumbTip = 4;
        public const int IndexMcp = 5, IndexPip = 6, IndexDip = 7, IndexTip = 8;
        public const int MiddleMcp = 9, MiddlePip = 10, MiddleDip = 11, MiddleTip = 12;
        public const int RingMcp = 13, RingPip = 14, RingDip = 15, RingTip = 16;
        public const int PinkyMcp = 17, PinkyPip = 18, PinkyDip = 19, PinkyTip = 20;
        public const int Count = 21;

        public static readonly int[] Bones =
        {
            0,1, 1,2, 2,3, 3,4, 0,5, 5,6, 6,7, 7,8, 5,9, 9,10, 10,11, 11,12,
            9,13, 13,14, 14,15, 15,16, 13,17, 0,17, 17,18, 18,19, 19,20
        };
    }

    public enum Handedness { Left, Right }

    /// <summary>Una mano en un cuadro.</summary>
    public class Hand
    {
        public Handedness Side;
        public float Score;
        /// <summary>Normalizados a la imagen: x,y en 0..1 (y hacia abajo), z relativo a la muñeca.</summary>
        public readonly Vector3[] Image = new Vector3[LM.Count];
        /// <summary>Métricos (m), origen aprox. en el centro de la mano. Y hacia abajo como MediaPipe.</summary>
        public readonly Vector3[] World = new Vector3[LM.Count];

        /// <summary>Centro de la palma en coordenadas de imagen (0..1).</summary>
        public Vector2 PalmCenter
        {
            get
            {
                var c = (Image[LM.Wrist] + Image[LM.IndexMcp] + Image[LM.MiddleMcp] + Image[LM.PinkyMcp]) * 0.25f;
                return new Vector2(c.x, c.y);
            }
        }

        public static Hand FromJson(HandJson j)
        {
            if (j == null || j.lm == null || j.lm.Length < LM.Count * 3) return null;
            var h = new Hand
            {
                Side = j.side == "Left" ? Handedness.Left : Handedness.Right,
                Score = j.score
            };
            bool hasWorld = j.wlm != null && j.wlm.Length >= LM.Count * 3;
            for (int i = 0; i < LM.Count; i++)
            {
                h.Image[i] = new Vector3(j.lm[i * 3], j.lm[i * 3 + 1], j.lm[i * 3 + 2]);
                h.World[i] = hasWorld
                    ? new Vector3(j.wlm[i * 3], j.wlm[i * 3 + 1], j.wlm[i * 3 + 2])
                    : h.Image[i] * 0.25f; // aproximación si el tracker no manda puntos métricos
            }
            return h;
        }
    }

    /// <summary>Un cuadro del tracker: 0, 1 o 2 manos.</summary>
    public class HandFrame
    {
        public float Time;
        public int Width, Height;
        public Hand Left, Right;
        public int Count => (Left != null ? 1 : 0) + (Right != null ? 1 : 0);
        public Hand Get(Handedness side) => side == Handedness.Left ? Left : Right;

        public static HandFrame FromPacket(HandPacket p)
        {
            var f = new HandFrame { Time = p.t, Width = p.w, Height = p.h };
            if (p.hands == null) return f;
            foreach (var hj in p.hands)
            {
                var h = Hand.FromJson(hj);
                if (h == null) continue;
                // Si llegan dos manos del mismo lado, nos quedamos con la de mayor confianza.
                if (h.Side == Handedness.Left) { if (f.Left == null || h.Score > f.Left.Score) f.Left = h; }
                else { if (f.Right == null || h.Score > f.Right.Score) f.Right = h; }
            }
            return f;
        }
    }

    // ---- Formato de cable (JsonUtility) ----
    [Serializable] public class HandJson { public string side; public float score; public float[] lm; public float[] wlm; }
    [Serializable] public class HandPacket { public float t; public int w; public int h; public HandJson[] hands; }

    /// <summary>Fuente de manos intercambiable (webcam+MediaPipe hoy; Quest XR Hands mañana).</summary>
    public interface IHandSource
    {
        /// <summary>Último cuadro recibido, o null si no hay.</summary>
        HandFrame Latest { get; }
        /// <summary>Segundos desde el último cuadro (Infinity si nunca llegó).</summary>
        float SecondsSinceLast { get; }
        float FramesPerSecond { get; }
        string Status { get; }
    }
}
