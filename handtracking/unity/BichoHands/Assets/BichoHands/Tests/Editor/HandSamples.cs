using Bicho.Hands;
using UnityEngine;

namespace Bicho.Hands.Tests
{
    /// <summary>Manos de prueba. La abierta es REAL: salió del tracker corriendo sobre IMG_7996.MOV del equipo.</summary>
    public static class HandSamples
    {
        public static readonly float[] OpenLm = { 0.1272f, 0.3244f, 0.0f, 0.0926f, 0.3197f, -0.0298f, 0.0689f, 0.308f, -0.0482f, 0.0592f, 0.2982f, -0.0637f, 0.0464f, 0.2927f, -0.0791f, 0.0878f, 0.2551f, -0.04f, 0.0753f, 0.2253f, -0.0607f, 0.0679f, 0.2061f, -0.0751f, 0.0635f, 0.1882f, -0.085f, 0.1259f, 0.2557f, -0.0417f, 0.1366f, 0.2232f, -0.0586f, 0.1444f, 0.2003f, -0.0726f, 0.1496f, 0.182f, -0.0818f, 0.156f, 0.2662f, -0.0455f, 0.1809f, 0.2495f, -0.0756f, 0.1818f, 0.2545f, -0.0911f, 0.1793f, 0.2612f, -0.0959f, 0.1775f, 0.2832f, -0.0507f, 0.1947f, 0.2824f, -0.0825f, 0.1843f, 0.2975f, -0.0912f, 0.172f, 0.312f, -0.0919f };
        public static readonly float[] OpenWlm = { 0.00243f, 0.07145f, 0.0753f, -0.02276f, 0.05701f, 0.04111f, -0.03853f, 0.04758f, 0.0117f, -0.04188f, 0.03865f, -0.03326f, -0.0468f, 0.02042f, -0.05604f, -0.03198f, -0.00513f, -0.00286f, -0.03607f, -0.03309f, -0.01467f, -0.03618f, -0.05157f, -0.02318f, -0.04066f, -0.0642f, -0.04773f, -0.00513f, -0.00401f, 0.00146f, 0.00331f, -0.03879f, -0.01511f, 0.00157f, -0.05912f, -0.03635f, -0.00147f, -0.07781f, -0.06654f, 0.02165f, 0.00122f, 0.00201f, 0.0273f, -0.01138f, -0.0205f, 0.02444f, -0.01243f, -0.048f, 0.01882f, -0.00137f, -0.07035f, 0.03487f, 0.02181f, 0.00637f, 0.03916f, 0.01895f, -0.00867f, 0.02875f, 0.03059f, -0.01892f, 0.01931f, 0.04937f, -0.02584f };

        public static Hand Open() => Hand.FromJson(new HandJson { side = "Right", score = 1.0f, lm = (float[])OpenLm.Clone(), wlm = (float[])OpenWlm.Clone() });

        static void Set(Hand h, int i, Vector3 world, Vector3 image) { h.World[i] = world; h.Image[i] = image; }

        /// <summary>Dobla un dedo: la punta y la falange media vuelven hacia la palma.</summary>
        public static void Curl(Hand h, int mcp, int pip, int dip, int tip)
        {
            Vector3 w = h.World[LM.Wrist], m = h.World[mcp];
            Vector3 wi = h.Image[LM.Wrist], mi = h.Image[mcp];
            Set(h, pip, Vector3.Lerp(m, w, -0.25f), Vector3.Lerp(mi, wi, -0.25f));
            Set(h, dip, Vector3.Lerp(m, w, 0.05f), Vector3.Lerp(mi, wi, 0.05f));
            Set(h, tip, Vector3.Lerp(m, w, 0.25f), Vector3.Lerp(mi, wi, 0.25f));
        }

        public static void TuckThumb(Hand h)
        {
            Vector3 t = Vector3.Lerp(h.World[LM.IndexMcp], h.World[LM.MiddleMcp], 0.5f);
            Vector3 ti = Vector3.Lerp(h.Image[LM.IndexMcp], h.Image[LM.MiddleMcp], 0.5f);
            Set(h, LM.ThumbIp, Vector3.Lerp(h.World[LM.ThumbMcp], t, 0.5f), Vector3.Lerp(h.Image[LM.ThumbMcp], ti, 0.5f));
            Set(h, LM.ThumbTip, t, ti);
        }

        public static Hand Fist()
        {
            var h = Open();
            Curl(h, LM.IndexMcp, LM.IndexPip, LM.IndexDip, LM.IndexTip);
            Curl(h, LM.MiddleMcp, LM.MiddlePip, LM.MiddleDip, LM.MiddleTip);
            Curl(h, LM.RingMcp, LM.RingPip, LM.RingDip, LM.RingTip);
            Curl(h, LM.PinkyMcp, LM.PinkyPip, LM.PinkyDip, LM.PinkyTip);
            TuckThumb(h);
            return h;
        }

        public static Hand Point()
        {
            var h = Open();
            Curl(h, LM.MiddleMcp, LM.MiddlePip, LM.MiddleDip, LM.MiddleTip);
            Curl(h, LM.RingMcp, LM.RingPip, LM.RingDip, LM.RingTip);
            Curl(h, LM.PinkyMcp, LM.PinkyPip, LM.PinkyDip, LM.PinkyTip);
            TuckThumb(h);
            return h;
        }

        public static Hand Victory()
        {
            var h = Open();
            Curl(h, LM.RingMcp, LM.RingPip, LM.RingDip, LM.RingTip);
            Curl(h, LM.PinkyMcp, LM.PinkyPip, LM.PinkyDip, LM.PinkyTip);
            TuckThumb(h);
            return h;
        }

        /// <summary>«OK»: punta del índice sobre la punta del pulgar, los otros tres dedos estirados.</summary>
        public static Hand Pinch()
        {
            var h = Open();
            Vector3 mid = Vector3.Lerp(h.World[LM.ThumbTip], h.World[LM.IndexTip], 0.5f);
            Vector3 midi = Vector3.Lerp(h.Image[LM.ThumbTip], h.Image[LM.IndexTip], 0.5f);
            Set(h, LM.ThumbTip, mid, midi);
            Set(h, LM.IndexTip, mid + new Vector3(0.004f, 0, 0), midi);
            return h;
        }
    }
}
