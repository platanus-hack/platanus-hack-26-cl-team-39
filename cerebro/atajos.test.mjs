import assert from 'node:assert/strict'
import test from 'node:test'
import { atajoOido } from './atajos.mjs'

const opciones = { fw: '0.37.0' }

test('giro dirigido al bicho, incluso al final de una transcripción de la sala', () => {
  for (const texto of [
    'Bicho gira', 'Píchu, gira', '¡Bitcho, gira!',
    'Siguen conversando. Bicho, gira.',
    'No gastemos tanto dinero, tranquilo. Baby, ¿bicho gira?',
  ]) assert.equal(atajoOido(texto, opciones)?.cmd.giro, 'derecha', texto)
  assert.equal(atajoOido('Oye, Bicho, gira a la izquierda', opciones)?.cmd.giro, 'izquierda')
})

test('conserva las negaciones, citas, preguntas largas y límites del firmware', () => {
  for (const texto of [
    'No, bicho gira', 'Si yo digo bicho gira', 'Bicho, no gires', 'Ella dijo «bicho gira».',
    'Hay ruido. Ella preguntó, ¿Bicho gira?', 'Dicen. «Bicho gira».',
    '¿Bicho gira o avanza?', 'Hay que ver. ¿El bicho gira solo?',
    'Están hablando. Bicho prende los motores',
  ]) assert.equal(atajoOido(texto, opciones), null, texto)
  assert.equal(atajoOido('Bicho, gira', { fw: '0.34.0' }), null)
})
