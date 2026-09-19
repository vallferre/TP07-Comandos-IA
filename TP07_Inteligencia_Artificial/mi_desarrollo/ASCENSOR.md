# Caso real: el robot se desestabiliza en el ascensor

En el G1/Go2 físico, al entrar a un ascensor y que la cabina acelere o frene,
el robot se tambalea. El simulador de este TP es cinemático (no tiene física),
así que el escenario **recrea el síntoma y la causa**, no un contacto de
zapatos contra el piso.

## Por qué pasa

El controlador de equilibrio lee el IMU. El acelerómetro no mide “gravedad”:
mide aceleración propia. En un piso quieto eso es ~9.81 m/s² hacia abajo. En
un ascensor que arranca se suma la aceleración de la cabina (típicamente
0.8–1.5 m/s²).

El controlador interpreta ese pico como “me estoy cayendo / inclinando” y
corrige con un paso o un ladeo. El piso, en realidad, está subiendo con él.
Esa corrección es la que lo desestabiliza.

Caminar en ese instante lo empeora: el pie busca un piso que el IMU ya no
describe bien.

## Cómo evitarlo (en el robot real y acá)

1. Entrar y **frenar por completo**.
2. Pasar a un modo de hold / damp / “no caminar”: congelar locomoción.
3. **Ignorar el transitorio vertical del IMU** (o no usar ese `az` para
   balance) mientras `|az − g|` sea grande.
4. Esperar crucero o que las puertas abran (`az ≈ 0`).
5. Recién ahí soltar el modo y caminar.

Eso es el **modo seguro** del escenario.

## Cómo verlo

1. Abrí `INICIAR_SIMULADOR.bat` y dejá la ventana abierta.
2. **El fallo:** doble clic en `DEMO_ASCENSOR.bat` y elegí `1`.
   El robot entra, la cabina acelera, se tambalea y cae.
3. **La solución:** de nuevo el `.bat` y elegí `2`.
   Entra, congela el equilibrio, viaja de pie.

O desde el modo interactivo de `mi_tp07.py`, después de la tabla:

```
  > entrá al ascensor
  > entrá al ascensor en modo seguro
```

Cerrá y reabrí el simulador la primera vez: el escenario vive en ese proceso.
