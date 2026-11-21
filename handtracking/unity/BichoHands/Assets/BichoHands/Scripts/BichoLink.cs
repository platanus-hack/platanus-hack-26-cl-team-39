using System;
using System.Collections.Concurrent;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace Bicho.Hands
{
    /// <summary>Telemetría que manda el bicho: {"t":"s","ms":…,"d":{…}} (mismo formato que el panel Bicho Dev).</summary>
    [Serializable] public class BichoImu { public float pitch; public float roll; }
    [Serializable] public class BichoData { public float mic; public BichoImu imu; public float dist_cm = -1; public int[] servo; public float temp_cpu; public bool boton; }
    [Serializable] public class BichoMsg
    {
        public string t; public long ms; public BichoData d; public string name; public string fw;
        public bool bicho; public bool puedeMandar;   // {"t":"rele","bicho":true,"puedeMandar":true}
        public string lvl; public string msg;          // {"t":"log","lvl":"warn","msg":"…"}
    }

    /// <summary>
    /// Conexión WebSocket con el bicho, directa (ws://&lt;ip-de-la-pi&gt;:8080/ws, misma red) o por el relé
    /// (wss://&lt;relé&gt;/ws?clave=…, desde cualquier red; ver PROTOCOLO.md). Es el mismo canal de bicho·dev.
    /// Un solo hilo de envío (ClientWebSocket no admite envíos concurrentes). El comando de manejo es
    /// «último gana»: si el envío se atrasa, se descarta el viejo y se manda el más reciente.
    /// </summary>
    public class BichoLink : MonoBehaviour
    {
        public const int DefaultPort = 8080;
        const int MaxLine = 64 * 1024;

        [Tooltip("IP de la Raspberry Pi (puerto 8080), o https://<relé> para entrar por el relé")]
        public string host = "bicho.local";

        [Tooltip("Clave del equipo (la del inventario). Solo la pide el relé para mandar comandos.")]
        public string clave = "";

        /// <summary>true si la conexión es por el relé (https/wss o *.trycloudflare.com).</summary>
        public bool IsRelay { get; private set; }
        /// <summary>Por el relé: si el bicho está conectado al relé. Directo: siempre true.</summary>
        public bool BichoOnline { get; private set; } = true;
        /// <summary>Por el relé: si la clave sirvió para mandar comandos.</summary>
        public bool CanCommand { get; private set; } = true;
        public string LastLog { get; private set; }

        public bool IsConnected => _ws != null && _ws.State == WebSocketState.Open;
        public string Status { get; private set; } = "desconectado";
        public BichoMsg LastTelemetry { get; private set; }
        public BichoMsg Info { get; private set; }
        public int Sent { get; private set; }

        ClientWebSocket _ws;
        CancellationTokenSource _cts;
        readonly ConcurrentQueue<string> _outbox = new ConcurrentQueue<string>();
        readonly ConcurrentQueue<string> _inbox = new ConcurrentQueue<string>();
        string _latestDrive;          // slot «último gana»
        readonly object _driveLock = new object();
        readonly AutoResetEvent _wake = new AutoResetEvent(false);

        public static bool LooksLikeRelay(string host)
        {
            var h = host.Trim().ToLowerInvariant();
            return h.StartsWith("https://") || h.StartsWith("wss://") || h.Contains(".trycloudflare.com");
        }

        public static string Url(string host, string clave = null)
        {
            bool relay = LooksLikeRelay(host);
            var h = host.Trim();
            foreach (var pre in new[] { "ws://", "wss://", "http://", "https://" })
                if (h.StartsWith(pre)) h = h.Substring(pre.Length);
            int slash = h.IndexOf('/');
            if (slash >= 0) h = h.Substring(0, slash);
            if (relay)
                return $"wss://{h}/ws" + (string.IsNullOrWhiteSpace(clave) ? "" : "?clave=" + Uri.EscapeDataString(clave.Trim()));
            if (!h.Contains(":")) h += ":" + DefaultPort;
            return $"ws://{h}/ws";
        }

        public void Connect()
        {
            Disconnect();
            _cts = new CancellationTokenSource();
            var url = Url(host, clave);
            IsRelay = LooksLikeRelay(host);
            BichoOnline = !IsRelay; CanCommand = true; LastLog = null;
            Status = "conectando a " + (IsRelay ? "relé " : "") + url.Split('?')[0] + "…";
            _ = Run(new Uri(url), _cts.Token);
        }

        public void Disconnect()
        {
            if (_ws != null && _ws.State == WebSocketState.Open) SendNow("{\"cmd\":\"stop\"}", 300);
            _cts?.Cancel();
            try { _ws?.Abort(); } catch { }
            _ws = null;
            Status = "desconectado";
        }

        async Task Run(Uri uri, CancellationToken ct)
        {
            var ws = new ClientWebSocket();
            ws.Options.KeepAliveInterval = TimeSpan.FromSeconds(5);
            _ws = ws;
            try
            {
                using (var timeout = CancellationTokenSource.CreateLinkedTokenSource(ct))
                {
                    timeout.CancelAfter(IsRelay ? 8000 : 4000);
                    await ws.ConnectAsync(uri, timeout.Token);
                }
                Status = (IsRelay ? "conectado al relé · " : "conectado · ") + uri.Host;
                Enqueue("{\"cmd\":\"info\"}");
                var send = Task.Run(() => SendLoop(ws, ct));
                await ReceiveLoop(ws, ct);
                await send;
            }
            catch (Exception e)
            {
                if (!ct.IsCancellationRequested) Status = "error: " + e.Message;
            }
            finally
            {
                if (_ws == ws && !ct.IsCancellationRequested) Status = "se cortó la conexión";
            }
        }

        async Task ReceiveLoop(ClientWebSocket ws, CancellationToken ct)
        {
            var buf = new byte[16 * 1024];
            var ms = new System.IO.MemoryStream();
            while (ws.State == WebSocketState.Open && !ct.IsCancellationRequested)
            {
                var r = await ws.ReceiveAsync(new ArraySegment<byte>(buf), ct);
                if (r.MessageType == WebSocketMessageType.Close) break;
                ms.Write(buf, 0, r.Count);   // bytes enteros: un carácter UTF-8 puede quedar partido entre trozos
                if (!r.EndOfMessage) continue;
                // Las imágenes de la cámara y la voz (cientos de KB) no le sirven a esta app: se descartan.
                if (ms.Length <= MaxLine)
                {
                    // El firmware puede mandar varias líneas JSON en un mensaje.
                    foreach (var line in Encoding.UTF8.GetString(ms.GetBuffer(), 0, (int)ms.Length).Split('\n'))
                        if (line.Trim().Length > 0) _inbox.Enqueue(line.Trim());
                }
                ms.SetLength(0);
            }
        }

        void SendLoop(ClientWebSocket ws, CancellationToken ct)
        {
            while (ws.State == WebSocketState.Open && !ct.IsCancellationRequested)
            {
                _wake.WaitOne(100);
                while (_outbox.TryDequeue(out var msg)) SendBlocking(ws, msg, ct);
                string drive;
                lock (_driveLock) { drive = _latestDrive; _latestDrive = null; }
                if (drive != null) SendBlocking(ws, drive, ct);
            }
        }

        void SendBlocking(ClientWebSocket ws, string msg, CancellationToken ct)
        {
            try
            {
                ws.SendAsync(new ArraySegment<byte>(Encoding.UTF8.GetBytes(msg)), WebSocketMessageType.Text, true, ct).Wait(ct);
                Sent++;
            }
            catch (Exception e) { if (!ct.IsCancellationRequested) Status = "error al enviar: " + e.Message; }
        }

        /// <summary>Envío inmediato (para STOP al salir); bloquea como máximo timeoutMs.</summary>
        void SendNow(string msg, int timeoutMs)
        {
            try
            {
                _ws.SendAsync(new ArraySegment<byte>(Encoding.UTF8.GetBytes(msg)), WebSocketMessageType.Text, true, CancellationToken.None).Wait(timeoutMs);
            }
            catch { }
        }

        /// <summary>Comando que no se puede perder (stop, servo, gesto, info).</summary>
        public void Enqueue(string json) { _outbox.Enqueue(json); _wake.Set(); }

        /// <summary>Comando de manejo: solo importa el más reciente.</summary>
        public void SetDrive(string json) { lock (_driveLock) _latestDrive = json; _wake.Set(); }

        void Update()
        {
            while (_inbox.TryDequeue(out var line))
            {
                if (!line.StartsWith("{")) continue;
                try
                {
                    var m = JsonUtility.FromJson<BichoMsg>(line);
                    if (m == null) continue;
                    if (m.t == "s") LastTelemetry = m;
                    else if (m.t == "info") { Info = m; BichoOnline = true; }
                    else if (m.t == "rele")
                    {
                        BichoOnline = m.bicho;
                        // El aviso de conexión trae puedeMandar; el de «se cayó/volvió el bicho» no.
                        if (line.Contains("puedeMandar")) CanCommand = m.puedeMandar;
                    }
                    else if (m.t == "log" && !string.IsNullOrEmpty(m.msg)) LastLog = m.msg;
                }
                catch { /* línea de log del firmware, no JSON */ }
            }
        }

        void OnApplicationQuit() => Disconnect();
        void OnDisable() => Disconnect();
    }
}
