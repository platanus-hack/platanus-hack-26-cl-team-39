using NUnit.Framework;
using UnityEngine;

namespace Bicho.Hands.Tests
{
    public class BichoHandsTests
    {
        [Test] public void ManoRealAbierta_EsPalma() => Assert.AreEqual(Gesture.OpenPalm, GestureRecognizer.Classify(HandSamples.Open()).Gesture);
        [Test] public void Puno_EsPuno() => Assert.AreEqual(Gesture.Fist, GestureRecognizer.Classify(HandSamples.Fist()).Gesture);
        [Test] public void Indice_EsIndice() => Assert.AreEqual(Gesture.Point, GestureRecognizer.Classify(HandSamples.Point()).Gesture);
        [Test] public void Victoria_EsVictoria() => Assert.AreEqual(Gesture.Victory, GestureRecognizer.Classify(HandSamples.Victory()).Gesture);
        [Test] public void Ok_EsPinza() => Assert.AreEqual(Gesture.Pinch, GestureRecognizer.Classify(HandSamples.Pinch()).Gesture);

        [Test] public void ZonaMuerta_NoMueve()
        {
            BichoHandController.Joystick(new Vector2(0.52f, 0.47f), 0.07f, 0.25f, out var t, out var r);
            Assert.AreEqual(0f, t); Assert.AreEqual(0f, r);
        }

        [Test] public void PalmaArriba_Avanza()
        {
            BichoHandController.Joystick(new Vector2(0.5f, 0.2f), 0.07f, 0.25f, out var t, out var r);
            Assert.AreEqual(1f, t, 1e-4f); Assert.AreEqual(0f, r);
        }

        [Test] public void Mezcla_GiroDerecha_RuedaIzqMasRapida()
        {
            BichoHandController.Mix(0.5f, 0.3f, out var l, out var r);
            Assert.Greater(l, r);
            BichoHandController.Mix(1f, 1f, out l, out r);
            Assert.LessOrEqual(Mathf.Abs(l), 1f); Assert.LessOrEqual(Mathf.Abs(r), 1f);
        }

        [Test] public void Estabilizador_ExigeVariosCuadros()
        {
            var s = new GestureStabilizer { framesToConfirm = 3 };
            Assert.IsFalse(s.Push(Gesture.Fist)); Assert.IsFalse(s.Push(Gesture.Fist));
            Assert.IsTrue(s.Push(Gesture.Fist)); Assert.AreEqual(Gesture.Fist, s.Stable);
            Assert.IsFalse(s.Push(Gesture.OpenPalm)); Assert.AreEqual(Gesture.Fist, s.Stable);
        }

        [Test] public void Url_AgregaPuertoYRuta()
        {
            Assert.AreEqual("ws://192.168.1.50:8080/ws", BichoLink.Url("192.168.1.50"));
            Assert.AreEqual("ws://bicho.local:9000/ws", BichoLink.Url("http://bicho.local:9000/"));
            Assert.AreEqual("wss://x.trycloudflare.com/ws", BichoLink.Url("https://x.trycloudflare.com/"));
            Assert.AreEqual("wss://x.trycloudflare.com/ws?clave=a%20b", BichoLink.Url("x.trycloudflare.com", "a b"));
            Assert.AreEqual("ws://192.168.1.50:8080/ws", BichoLink.Url("192.168.1.50", "ignorada"));
            Assert.AreEqual("si", BichoHandController.LightFor(Gesture.ThumbsUp));
            Assert.AreEqual(null, BichoHandController.LightFor(Gesture.OpenPalm));
        }
    }
}
