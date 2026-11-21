# bicho·dev

Herramienta interna del equipo para el software del bicho (un Raspberry Pi 3 con [`bichod`](../bicho/)):

- muestra la **versión cargada** en el bicho y **qué hace**;
- muestra la **versión disponible** y la **instala** por WiFi con un botón;
- muestra la **versión de la web** (arriba a la derecha);
- grafica los **sensores en tiempo real** (clic en uno para ampliarlo);
- tiene una **consola** para ver los mensajes del bicho y mandarle comandos;
- trae un **simulador** para trabajar sin el bicho prendido.

El bicho y la web se hablan con el contrato de [`../PROTOCOLO.md`](../PROTOCOLO.md).

## Correrla

```bash
npm install && npm run dev
```

Abre <http://localhost:5173>. En la barra lateral, en **Conexión**:

- **WiFi:** escribe `bicho.local` o la IP del Pi (el puerto 8080 se agrega solo). Corre la web en `localhost`: desde un sitio HTTPS el navegador bloquea la conexión con el Pi.
- **Simulador:** datos falsos para desarrollar la interfaz.

Para instalar un paquete `.tar.gz` que tengas en tu computador, suéltalo en cualquier parte de la página.

## Publicar una versión del bicho

1. Sube `version` en [`../bicho/version.json`](../bicho/version.json).
2. Corre:

```bash
npm run release -- --notes "Agrega el micrófono"
```

El paquete queda en `public/firmware/<versión>/` y se agrega a `manifest.json`. La web lo muestra como disponible en unos 10 segundos y avisa a quien la tenga abierta. Haz commit de `public/firmware/` para que el resto del equipo también lo vea.
