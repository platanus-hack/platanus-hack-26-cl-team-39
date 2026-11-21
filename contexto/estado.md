# Estado del proyecto

_Lo actualiza el Claude de cualquiera cuando algo cambia. Máximo ~50 líneas: lo viejo se borra de aquí (queda en la bitácora). Última actualización: 21 nov, 04:35, Guty (Claude)._

## La idea

El **bicho**: un robot sobre un chasis 4WD de acrílico, con una Raspberry Pi 3 y sensores, sin control remoto. Lo maneja un agente Claude que además escribe y mejora su propio software (se "autoconstruye"). La lámpara robótica se descartó.

- Track **hardware**. El pitch: algo que parece imposible en 36 horas y que sale gracias a la IA.
- **Por decidir:** el caso de uso. Caminos en discusión: guardián de la propiedad (ahuyentar personas o animales que entran al terreno) o ayuda (adulto mayor, empresa).
- Reunión de las 4:04 (resumen de Granola): un solo brazo de 2 o 3 ejes basta (subir escalones, recoger cosas, prender una luz); parlante; sensor de luz abajo; sensor láser; la cámara tiene el cable corto.

## Qué está hecho

- **bicho·dev** ([`web/`](../web/)): versión del firmware y botón para actualizar por WiFi, sensores en vivo, consola, versiones, cronómetro de entrega e **inventario**.
- **bichod** ([`bicho/`](../bicho/)): agente Python con WebSocket de sensores y actualización por `POST /update`.
- **Inventario** en Neon, con 134 ítems sacados del Claude Sheet. Se ve en bicho·dev → Equipo → Inventario.
- **Harness del equipo:** este `CLAUDE.md`, `contexto/` y las skills compartidas.
- **Simulador 3D** en bicho·dev → Simulador, con el **idioma del bicho** (30 estados y 5 escenas) en [`bicho/lenguaje.json`](../bicho/lenguaje.json). Propuesta de Guty para que la ajusten Walls y Cristian.

## En qué está cada uno

_Reparto sugerido el 21 nov a las 00:01; cada uno corrige su línea._

- **Carlos:** firmware del bicho (siguiendo `PROTOCOLO.md`).
- **Renate:** cableado de sensores y nombres de los campos del panel.
- **Guty:** bicho·dev, inventario, harness del equipo y la comunicación agente → humano.
- **Walls y Cristian:** capa de IA y personalidad del bicho, y el pitch.

## Pendientes

- Elegir el caso de uso (guardián o ayuda).
- Corroborar que el esquemático (4 páginas) funciona con el hardware que hay.
- Revisar por qué el segundo inversor no aparece en el sistema.
- Publicar bicho·dev (lo ve quien hace los deploys) y conseguir una API key de Anthropic para el botón "Preguntar" del inventario.
- Llenar `platanus-hack-project.jsonc`, `project-description.md` y la URL de deploy antes de enviar.

## Fechas

- **Fin del hacking:** domingo 22 a las 8:30 según el cronograma; la plataforma cierra la entrega a las 9:00. Apuntar a tener todo listo a las 8:30. Se envía con un push a `main`, que lo hace una persona cuando el equipo decide.
- Sábado: desayuno 8:30, almuerzo 13:30, charla "Cómo hacer un buen demo" 20:00, comida 21:00.
- Domingo: último bajón 4:00, desayuno 8:00, presentaciones generales 9:30, finales 12:00, premiación 14:30.
- Cronograma completo: `web/src/lib/cronograma.json` (bicho·dev muestra el próximo evento bajo el cronómetro).
