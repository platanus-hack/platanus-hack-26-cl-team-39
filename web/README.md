# bicho·dev

Herramienta interna del equipo para el firmware del bicho:

- muestra la **versión de firmware cargada** en el bicho y **qué hace**;
- muestra la **versión disponible** y la **graba** por USB o WiFi;
- muestra la **versión de la web** (arriba a la derecha);
- grafica los **sensores en tiempo real** (clic en uno para ampliarlo);
- tiene una **consola** para leer el Serial y mandar comandos;
- trae un **simulador** para trabajar sin el bicho enchufado.

El bicho y la web se hablan con el contrato de [`../PROTOCOLO.md`](../PROTOCOLO.md).

## Correrla

```bash
npm install && npm run dev
```

Abre <http://localhost:5173> en **Chrome o Edge**: Web Serial no existe en Safari ni en Firefox.

En la barra lateral, en **Conexión**:

- **USB:** enchufa el ESP32 y elige el puerto. Sirve para monitorear y para grabar, aunque el firmware esté roto. La próxima vez basta con **Reconectar al último USB**, y si lo enchufas con la web abierta aparece un aviso para conectar.
- **WiFi:** escribe `bicho.local` o la IP. Solo funciona con la web en `localhost`, porque desde un sitio HTTPS el navegador bloquea `ws://`.
- **Simulador:** datos falsos para desarrollar la interfaz.

Para grabar un `.bin` que tengas en tu computador, suéltalo en cualquier parte de la página.

## Publicar una versión de firmware

```bash
npm run release -- --version 0.2.0 --notes "Agrega el micrófono" --dir ../firmware/bicho/build
```

Copia los `.bin` a `public/firmware/<versión>/` y actualiza `manifest.json`. La web la muestra como disponible en unos 10 segundos y le avisa a quien la tenga abierta.

Antes de compilar, sube `FW_VERSION` en el firmware: la web compara contra eso.
