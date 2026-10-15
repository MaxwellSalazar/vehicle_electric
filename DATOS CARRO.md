

#  Materiales Utilizados y Datos Técnicos

Implementación de un Sistema de Generación Fotovoltaico para la Asistencia de Carga Parcial en un Vehículo Eléctrico en el ISTER

16 de septiembre de 2026

##  Índice

1. Motor BLDC (Motor de transmisión media) 2

2. Paneles Fotovoltaicos Flexibles (BougeRV Arch100) 2

3. Controlador de Carga MPPT Boost (DC HOUSE 300 W) 4

4. Baterías de Gel (Banco de Almacenamiento) → 4

5. Otros componentes del sistema $\quad 5$




#  1. Motor BLDC (Motor de transmisión media)

Cuadro 1: Especificaciones técnicas del motor BLDC



| Parámetro | Valor | Unidad | Observación |
| --- | --- | --- | --- |
| Tipo | BLDC | – | Motor DC sin escobillas |
| Potencia nominal del motor | 2000 | W | Potencia eléctrica nominal (2 kW) |
| Voltaje nominal | 48 | V | Tensión nominal de operación |
| Eficiencia (conjunto inversor/controlador + motor) | 0.90 (90 %) | – | Rendimiento conjunto |
| Corriente máxima $(I_{mot max})$ | 46.3 | A | Calculada como $P_{dem}/V_{bat}$ = 2222,22 W/48 V |
| Corriente de diseño $(I_{dis})$ | 57.87 | A | Factor de protección del 125 % $(I_{mot max}$ × 1,25) |
| Demanda de potencia $(P_{dem})$ | 2222.22 | W | Considerando el 90 % de eficiencia del inversor/motor |


#  2. Paneles Fotovoltaicos Flexibles (BougeRV Arch100)

Configuración del arreglo (serie)

$\blacksquare$ Tensión de entrada MPPT ($V_{arr}$): 34.2 V (suma de $V_{mp}$: 17,1 V × 2)

$\blacksquare$ Tensión total de salida ajustada por temperatura: 32.87 V (16,43 V × 2)

$\blacksquare$ Corriente del arreglo: 5.85 A (se mantiene constante en serie)

- Potencia real neta ($P_{real}$): 170 W (ajustada por factor térmico $f_{temp} = 0,85$)

Ecuaciones asociadas

$$
P_{pv} = P_{stc} \times N_s \quad (1)
$$

$$
V_{arr} = V_{mp} \times N_s \quad (2)
$$

$$
V_{oc,tot} = V_{oc} \times N_s \quad (3)
$$

$$
P_{real} = P_{pv} \times f_{temp} \quad (4)
$$




Cuadro 2: Especificaciones técnicas de los paneles fotovoltaicos flexibles



| Parámetro | Valor | Unidad | Observación |
| --- | --- | --- | --- |
| Modelo | BougeRV | – | Panel flexible |
| Potencia nominal $(P_{stc})$ | Arch100 | W | Por módulo, en condicionesSTC |
| Cantidad $(N_{s})$ | 2 | unidades | Conectados en serie |
| Potencia nominal total | 200 | W | 2 × 100 W |
| Voltaje de máxima potencia$(V_{mp})$ | 17.1 | V | Por módulo |
| Voltaje de circuito abierto$(V_{oc})$ | 19.8 | V | Por módulo |
| Corriente de cortocircuito $(I_{sc})$ | 6.16 | A | Por módulo |
| Corriente a máxima potencia$(I_{mp})$ | 5.85 | A | Por módulo |
| Dimensiones | 100 × 60 | cm | Por módulo |
| Coeficiente de temperatura depotencia (γ) | -0.39 | %/°C | – |
| Coeficiente de temperatura devoltaje (β) | -0.065 | V/°C | – |
| Temperatura de operación nominal de celda (TONC) | 45.0 | °C | – |
| Eficiencia nominal $(η_{stc})$ | 18.0 | % | – |
| Tolerancia máxima de voltaje | 1000 | V DC | – |


Cuadro 3: Especificaciones técnicas del controlador MPPT Boost



| Parámetro | Valor | Unidad | Observación |
| --- | --- | --- | --- |
| Marca | DC HOUSE | - | - |
| Potencia | 300 | W | - |
| Tecnología | MPPT Boost | - | Elevador DC-DC con seguimiento de punto de máxima potencia |
| Rango de voltaje de entrada | 13 - 65 | V | Adecuado para paneles flexibles |
| Eficiencia de conversión $(η_{boost})$ | 0.99 (99 %) | - | - |
| Ciclo de trabajo (D) | 28.75 | % | Elevación de 34.2 V a 48 V |
| Corriente inyectada al bus $(I_{inj})$ | 3.51 | A | Corriente de carga hacia baterías/motor |
| Potencia neta transferida $(P_{out boost})$ | 170 × 0,99 ≈ 168,3 | W | $ P_{out}=P_{real}\times\eta_{boost} $ |





#  3. Controlador de Carga MPPT Boost (DC HOUSE 300 W)

##  Ecuaciones asociadas

$$
\frac{V_{bat}}{V_{arreglo}} = \frac{1}{1-D} \qquad (5)
$$

$$
D = 1 - \frac{V_{arreglo}}{V_{bat}} \qquad (6)
$$

$$
P_{out\_boost} = P_{real} \times \eta_{boost} \qquad (7)
$$

$$
I_{inj} = \frac{P_{out\, boost}}{V_{bateria}} \qquad (8)
$$

##  4. Baterías de Gel (Banco de Almacenamiento)

Cuadro 4: Especificaciones técnicas del banco de baterías de gel



| Parámetro | Valor | Unidad | Observación |
| --- | --- | --- | --- |
| Tipo | Gel | - | Batería DACAR GEL PO-WER |
| Configuración | 4 unidades en serie | - | 4 × 12 V = 48 V |
| Voltaje nominal del banco $(V_{bat})$ | 48 | V | Tensión nominal del bus de baterías |
| Capacidad comercial seleccionada | 60 | Ah | Batería DACAR GEL PO-WER (48 V nominales) |
| Capacidad química calculada $(C_{Ah})$ | 55.38 | Ah | Para 1.0 h de autonomía con DoD = 85 % y $f_{s}$ = 1,1 |
| Profundidad de descarga máxima (DoD) | 85 | % | Porcentaje máximo de descarga permitido |
| Factor de seguridad $(f_{s})$ | 1.1 | - | Margen de sobredimensionamiento |
| Autonomía requerida | 1.0 | h | Tiempo de operación estimado a carga nominal |
| Potencia neta en batería $(P_{net})$ | 2053.92 | W | Potencia del motor menos aporte directo de paneles (170 W) |
| Energía total del banco | $ E=V_{tb}\times I_b= $$ P_{tc} $ | - | Producto de tensión nominal por capacidad |





#  Ecuaciones asociadas

$$
V_{banco} = V_{b1} + V_{b2} + V_{b3} + V_{b4} = V_{tb} \quad (9)
$$

$$
E = V_{tb} \times I_b = P_{tc} \quad (10)
$$

$$
P_{net} = P_{dem} - P_{out\, boost} \qquad (11)
$$

$$
E_{nom} = \frac{P_{net} \times t}{D_{OD}} \times f_s \quad (12)
$$

$$
C_{Ah} = \frac{E_{nom}}{V_{bat}} \qquad (13)
$$

#  5. Otros componentes del sistema

Cuadro 5: Componentes complementarios del sistema



| Componente | Especificación | Observación |
| --- | --- | --- |
| Conductores | Cobre, calibre 6 AWG (13.3 mm$^{2}$) | Sección mínima calculada: 4.42 mm$^{2}$; criterio NEC |
| Longitud del lazo | 4.0 m | Distancia total ida y vuelta |
| Caída de tensión máxima admisible (ΔV) | 3.0% | Equivalente al 3 % de $V_{bat}$ |
| Fusible del arreglo solar | 7.7 A | $I_{sc}$ × 1,25 = 6,16 A × 1,25 |
| Breaker principal DC | 57.87 A | Protege la línea principal del motor $(I_{dis})$ |
| Multímetro digital | CAT III 600 V, LCD retro-iluminado | Medición de tensión (AC/DC) hasta 600 V, corriente hasta 10 A, resistencia, continuidad y prueba de diodos |


##  Ecuaciones asociadas

$$
I_{dis} = I_{mot, max} \times K_{net} \quad (14)
$$

$$
S = \frac{2 \times c_{vpcu} \times L \times I_{mot \max}}{\Delta V_{max}} \quad (15)
$$

$$
i_{solar} \geq I_{sc} \times 1,25 \qquad (16)
$$

$$
i_{main} \geq I_{mot,max} \times 1,25 \quad (17)
$$




Cuadro 6: Parámetros geográficos y ambientales de la zona de estudio



| Parámetro | Valor | Unidad |
| --- | --- | --- |
| Día juliano del año (n) | 172 (21 de junio) | — |
| Latitud (φ) | -0.31 | ° |
| Índice de claridad atmosférica $(K_{t})$ | 0.55 | — |
| Temperatura ambiente $(T_{a})$ | 22.0 | °C |
| Declinación solar (δ) | 23.45 | ° |
| Ángulo horario de puesta de sol $(ω_{s})$ | 89.87 | ° |
| Irradiación extraterrestre diaria $(H_{0})$ | 9235.31 | Wh/m$^{2}$·día |
| Horas solar pico (HSP) | 5.08 | h |
| Irradiancia incidente pico (G) | 423.92 | $ \text{W/m}^2 $ |



