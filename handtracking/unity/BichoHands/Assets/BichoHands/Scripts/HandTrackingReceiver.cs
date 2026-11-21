using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;

namespace Bicho.Hands
{
    /// <summary>
    /// Recibe los cuadros del tracker (tracker/hand_tracker.py) por UDP en un hilo aparte.
    /// El hilo solo guarda el último paquete; el hilo principal lo lee sin bloquear.
    /// </summary>
    public class HandTrackingReceiver : MonoBehaviour, IHandSource
    {
        public int port = 5065;

        UdpClient _udp;
        Thread _thread;
        volatile bool _running;
        readonly object _lock = new object();
        HandFrame _pending;
        HandFrame _latest;
        double _lastRecv = double.NegativeInfinity;
        int _count;
        float _fps, _fpsT;
        string _status = "esperando tracker…";

        public HandFrame Latest => _latest;
        public float SecondsSinceLast => _latest == null ? float.PositiveInfinity : (float)(Time.realtimeSinceStartupAsDouble - _lastRecv);
        public float FramesPerSecond => _fps;
        public string Status => _status;

        void OnEnable()
        {
            try
            {
                _udp = new UdpClient(new IPEndPoint(IPAddress.Loopback, port));
                _udp.Client.ReceiveTimeout = 500;
                _running = true;
                _thread = new Thread(Loop) { IsBackground = true, Name = "HandTrackingReceiver" };
                _thread.Start();
                _status = $"escuchando udp://127.0.0.1:{port}";
            }
            catch (Exception e)
            {
                _status = $"no pude abrir el puerto {port}: {e.Message}";
                Debug.LogError("[Bicho] " + _status);
            }
        }

        void Loop()
        {
            var any = new IPEndPoint(IPAddress.Any, 0);
            while (_running)
            {
                try
                {
                    var bytes = _udp.Receive(ref any);
                    var pkt = JsonUtility.FromJson<HandPacket>(Encoding.UTF8.GetString(bytes));
                    if (pkt == null) continue;
                    var frame = HandFrame.FromPacket(pkt);
                    lock (_lock) { _pending = frame; }
                }
                catch (SocketException) { /* timeout: seguimos */ }
                catch (ObjectDisposedException) { return; }
                catch (Exception e) { Debug.LogWarning("[Bicho] paquete inválido: " + e.Message); }
            }
        }

        void Update()
        {
            HandFrame f = null;
            lock (_lock) { if (_pending != null) { f = _pending; _pending = null; } }
            if (f != null)
            {
                _latest = f;
                _lastRecv = Time.realtimeSinceStartupAsDouble;
                _count++;
            }
            _fpsT += Time.unscaledDeltaTime;
            if (_fpsT >= 1f) { _fps = _count / _fpsT; _count = 0; _fpsT = 0; }
            if (_running)
                _status = SecondsSinceLast < 1f ? $"tracker OK · {_fps:0} fps" : $"esperando tracker en udp {port}…";
        }

        void OnDisable()
        {
            _running = false;
            try { _udp?.Close(); } catch { }
            _thread?.Join(600);
            _udp = null;
        }
    }
}
