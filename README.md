# MiniProyecto 1 - Taller de Aplicación TIC I

Universidad de Concepción - Departamento de Ingeniería Eléctrica
Profesor: Vincenzo Caro Fuentes

**Integrantes:**
- Javier Espinoza Arcos
- Ignacio Aguilar Contreras

## Informe

El informe completo está en [`Taller_de_Aplicación_TIC_1.pdf)`](Taller_de_Aplicación_TIC_1.pdf).

## Videos demo

- **Parte 1 - Zona Safari Pokémon:** [ver video](https://drive.google.com/file/d/1uHgIACqxAN-m45fNmJyUKUS833GZz1YD/view?usp=sharing)
- **Parte 2 - Zona Safari Pokémon:** [ver video](https://drive.google.com/file/d/18k35rzbek4Gp644-cZqPESFK62zvnou2/view?usp=sharing)

## Actividad 1: Zona Safari Pokémon

Juego por consola en Raspberry Pi. Los hábitats disponibles dependen de la temperatura
y humedad medidas por un sensor DHT11, y se navega con un joystick leído mediante un
ADS1115. Dos LED RGB y un buzzer pasivo entregan retroalimentación de los eventos.

### Archivos

| `zona_safari.py` | Código completo del juego (Ítems 1.1 a 1.4) |


### Conexiones

| Componente | Pin del módulo | Raspberry Pi |
|---|---|---|
| DHT11 (KY-015) | S | GPIO 6 |
| Buzzer (KY-006) | S | GPIO 12 |
| LED RGB 1 (población) | R / G / B | GPIO 16 / 20 / 21 |
| LED RGB 2 (captura y combate) | R / G / B | GPIO 13 / 19 / 26 |
| ADS1115 | SDA / SCL | GPIO 2 / 3 |
| Joystick (KY-023) | VRy / VRx | A0 / A1 del ADS1115 |

Todos los módulos se alimentan desde 3.3 V y comparten GND.


## Actividad 2: Consola de juegos retro

Instalación de RetroPie en una Raspberry Pi 3. El tutorial paso a paso está en el informe.
Sistemas probados: Super Nintendo (Super Mario World) y Nintendo 64 (Mario Kart 64).
