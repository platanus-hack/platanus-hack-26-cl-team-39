# harness: el cerebro del bicho

El harness es la capa de IA: lo que escucha, piensa y decide qué hace el bicho. El agente del bicho (`bicho/`) solo expone sensores y actuadores; la personalidad y las decisiones viven acá.

## Qué hace

1. **Escucha**: lee los sensores del bicho (micrófono, IMU, botones) y, si hace falta, audio o cámara del computador.
2. **Piensa**: le pasa el contexto a un modelo (Claude) con una personalidad y un set de herramientas.
3. **Actúa**: traduce lo que decide el modelo en comandos para el bicho (servos, LEDs, sonido).

## Cómo se conecta al bicho

Usa el mismo contrato que la web, descrito en [`../PROTOCOLO.md`](../PROTOCOLO.md):

- Se conecta a `ws://bicho.local:8080/ws` (o a la IP que reporta `info`).
- Recibe los frames `{"t":"s",...}` con los sensores y los `{"t":"info",...}` con la versión.
- Manda comandos `{"cmd":"..."}`. Los comandos propios del bicho (por ejemplo `{"cmd":"servo","i":0,"deg":90}`) se definen en `manejar()` de `bicho/comandos.py`.

Así el harness, la web y el agente del bicho se pueden desarrollar por separado: si se respeta el protocolo, todo encaja.

## Estado

Por armar. Falta decidir el lenguaje (TypeScript o Python) y la idea final del bicho.

Dueños sugeridos: Walls y Cristian.
