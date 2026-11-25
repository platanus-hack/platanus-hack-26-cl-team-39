# Pinza de dos dedos (P30 a P34)

Reemplaza la muñeca y el dedo único (P11, P14 y P15). Dos dedos cierran al mismo tiempo gracias a un par de engranajes, movidos por un solo MG90S. Va atornillada al costado del eslabón 2 (P10) **tal como está**: no hay que reimprimirlo. El alojamiento de la punta del eslabón queda vacío.

El brazo queda con 4 servos: giro, hombro y codo (grandes) y pinza (MG90S). Sobran un servo grande y dos MG90S.

## Qué imprimir

Todo en PETG con el perfil PETG-MECÁNICA de [`IMPRIMIR.md`](IMPRIMIR.md), sin soportes. Son unos 45 g en total.

| Pieza | Archivo | Cómo va en la cama |
|---|---|---|
| P30 · Palma | `STL/P30_palma_de_la_pinza.stl` | Como viene: la placa abajo y la pestaña hacia arriba. |
| P31 · Dedo motriz | `STL/P31_dedo_motriz.stl` | Como viene: el rebaje del horn hacia la cama. |
| P32 · Dedo conducido | `STL/P32_dedo_conducido.stl` | Como viene. |
| P33 · Buje | `STL/P33_buje_del_dedo.stl` | Parado. |
| P34 · Contraplaca | `STL/P34_contraplaca.stl` | El nervio hacia arriba. |

Los dientes son de módulo 1,5, con 0,3 mm de juego entre ejes. Si los engranajes quedan apretados, lija los flancos o imprime los dedos con compensación horizontal de −0,1 mm.

## Tornillos

- 2 M3×12 con tuerca: palma al eslabón 2.
- 1 M3×25 (o más largo) con 2 tuercas: eje del dedo conducido.
- Los tornillos del MG90S: 2 de las orejas, 2 chicos del horn y el central.

## Armado

1. Mete a presión las 2 tuercas M3 en los hexágonos de la pestaña de la palma.
2. Apoya la pestaña contra la cara plana del eslabón 2 (la que no tiene el alojamiento), con la placa descansando sobre el canto de arriba. Por el otro lado pon la contraplaca, con el nervio dentro de la ranura, y aprieta los 2 M3×12. **Hazlo antes de montar el servo**, que después tapa un tornillo.
3. Mete el MG90S por abajo de la placa, con el eje hacia arriba y hacia la punta. Atorníllalo por las orejas.
4. Atornilla el horn de un brazo al rebaje del dedo motriz con los 2 tornillos chicos (muerden en la ranura). Una gota de cianoacrilato ayuda.
5. Pasa el M3 largo por la placa desde abajo, y encima pon el buje y el dedo conducido. Cierra con 2 tuercas apretadas una contra la otra, dejando que el dedo gire libre.
6. Deja el servo en la posición de «cerrado» con el tester. Calza el dedo motriz en el eje con la pinza cerrada (las puntas tocándose) y pon el tornillo central por el agujero de arriba.
7. Forra las caras que aprietan con algo que no resbale: elástico, termorretráctil o gotas de silicona caliente.

## Qué puede agarrar

- Objetos de **15 a 60 mm de ancho** y hasta unos **100 g**. Abre hasta unos 10 cm.
- El MG90S aprieta con unos 200 g de fuerza en la mitad del dedo. Alcanza para cosas livianas que no resbalen; los ganchos de las puntas ayudan a que no se escapen.
- El brazo **no llega al suelo**: el hombro queda a unos 22 cm de alto y el alcance es de 21 cm. Para el demo, el objeto va parado sobre una base de 20 a 30 cm de alto, o se lo pasa una persona.
- Sin muñeca, la pinza queda horizontal solo cuando el eslabón 2 está horizontal. A esa altura es donde mejor agarra.

Si hace falta apretar más fuerte, la alternativa es mover la pinza con el servo grande que sobra: pide regenerar la palma con otro alojamiento.

## Regenerar

```bash
/Applications/Blender.app/Contents/MacOS/Blender -b -P diseno/blender/generar_pinza.py -- diseno/imprimir/STL
```

Las medidas están al inicio de [`../blender/generar_pinza.py`](../blender/generar_pinza.py). No se ha impreso todavía: prueba primero el calce del horn y de los engranajes.
