# =========================================================
# ZONA SAFARI POKÉMON - MiniProyecto 1 (Taller de Aplicación TIC I)
# Ítems 1.1, 1.2, 1.3 y 1.4
# =========================================================
import time
import os
import random
import board
import busio
import adafruit_dht
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from gpiozero import TonalBuzzer, RGBLED
from gpiozero.tones import Tone
import subprocess

# =========================================================
# CONFIGURACIÓN DE PINES GPIO
# =========================================================
PIN_DHT11 = 6             # GPIO 6  - Sensor DHT11
PIN_BUZZER = 12           # GPIO 12 - Buzzer pasivo

# LED RGB 1: indicador de población del hábitat (primer LED, Ítem 1.2)
PIN_RGB1_R = 16
PIN_RGB1_G = 20
PIN_RGB1_B = 21

# LED RGB 2: resultado de captura y combate (segundo LED, Ítems 1.3 y 1.4)
PIN_RGB2_R = 13
PIN_RGB2_G = 19
PIN_RGB2_B = 26

# Ambos LED RGB son de cátodo común (pin común a GND).
# Si fueran de ánodo común (pin común a 3.3V), cambiar esto a False.
RGB_CATODO_COMUN = True

# =========================================================
# CONSTANTES DEL JUEGO
# =========================================================
MAX_EQUIPO = 6            # Máximo de Pokémon en el equipo
AUMENTO_COMIDA = 0.15     # Cuánto sube la probabilidad al dar de comer (15%)
CURACION_DESCANSO = 15    # [MEJORA] HP que recupera el equipo al descansar

# Colores de los LED RGB (rojo, verde, azul), cada valor va de 0 a 1
VERDE = (0, 1, 0)
ROJO = (1, 0, 0)
AZUL = (0, 0, 1)
AMARILLO = (1, 1, 0)
CELESTE = (0, 1, 1)
MORADO = (1, 0, 1)
BLANCO = (1, 1, 1)

# Colores del LED RGB 1 (población del hábitat)
COLOR_HAY_POKEMON = VERDE    # quedan Pokémon en el hábitat
COLOR_AGOTADO = ROJO         # la población total llegó a 0

# Sonidos del buzzer: lista de (frecuencia en Hz, duración en segundos)
# Frecuencia 0 = silencio.
# Ojo: el TonalBuzzer por defecto solo acepta entre 220 Hz y 880 Hz
SONIDOS = {
    "navegar":         [(330, 0.08)],
    "confirmar":       [(440, 0.15)],
    "aparicion":       [(523, 0.10), (659, 0.10), (784, 0.20)],
    "comida":          [(392, 0.08), (0, 0.05), (392, 0.08)],
    "exito":           [(523, 0.08), (659, 0.08), (784, 0.08), (659, 0.08), (784, 0.35)],
    "fallo":           [(392, 0.15), (330, 0.15), (262, 0.30)],
    "escape":          [(494, 0.06), (0, 0.04), (494, 0.06), (0, 0.04), (494, 0.06)],
    "efectivo":        [(659, 0.07), (784, 0.18)],
    "victoria":        [(392, 0.12), (523, 0.12), (659, 0.12), (784, 0.12), (0, 0.05), (784, 0.35)],
    "derrota":         [(392, 0.30), (349, 0.30), (294, 0.30), (233, 0.50)],
    "captura_combate": [(784, 0.10), (784, 0.10), (659, 0.10), (784, 0.35)],
    "debilitado":      [(247, 0.20), (0, 0.05), (247, 0.20), (0, 0.05), (233, 0.40)],
}

# Tabla de efectividad de tipos (triángulo Fuego -> Planta -> Agua -> Fuego)
# Si una combinación no está aquí, el daño es normal (x1)
EFECTIVIDAD = {
    ("Fuego", "Planta"): 2,
    ("Planta", "Agua"): 2,
    ("Agua", "Fuego"): 2,
    ("Planta", "Fuego"): 0.5,
    ("Agua", "Planta"): 0.5,
    ("Fuego", "Agua"): 0.5,
}

# =========================================================
# VARIABLES GLOBALES DEL JUEGO
# =========================================================
equipo_jugador = []   # Almacenará hasta 6 Pokémon capturados

# =========================================================
# INICIALIZACIÓN DE HARDWARE
# =========================================================
print("Inicializando sensores... (puede tomar unos segundos)")

subprocess.run(
    ["bash", "correct_sensor.sh"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# Sensor DHT11 (convierte el número 6 en board.D6)
pin_dht = getattr(board, f"D{PIN_DHT11}")
sensor_dht = adafruit_dht.DHT11(pin_dht, use_pulseio=True)

# Joystick leído a través del ADS1115 (por I2C)
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
eje_y = AnalogIn(ads, 0)
eje_x = AnalogIn(ads, 1)

# LED RGB 1: población del hábitat
led_disp = RGBLED(red=PIN_RGB1_R, green=PIN_RGB1_G, blue=PIN_RGB1_B,
                  active_high=RGB_CATODO_COMUN)
# LED RGB 2: captura y combate
led_rgb = RGBLED(red=PIN_RGB2_R, green=PIN_RGB2_G, blue=PIN_RGB2_B,
                 active_high=RGB_CATODO_COMUN)
# Buzzer
buzzer = TonalBuzzer(PIN_BUZZER)

led_disp.off()
led_rgb.off()

# =========================================================
# BASE DE DATOS DE HÁBITATS Y POKÉMON (Ítem 1.1)
# =========================================================
# Cada hábitat tiene rangos de temperatura (°C) y humedad (%).
#  - Desierto y Cueva se diferencian principalmente por TEMPERATURA
#  - Pradera y Playa se diferencian principalmente por HUMEDAD
# Con estos rangos siempre hay al menos un hábitat disponible:
#  - hasta 18°C  -> Cueva
#  - 19 a 24°C   -> Pradera y/o Playa (según la humedad)
#  - desde 25°C  -> Desierto (y a veces Pradera/Playa)
# Población: 3 = común, 2 = menos frecuente, 1 = especial
habitats = [
    {
        "nombre": "Desierto",
        "temp_min": 25, "temp_max": 50,
        "humedad_min": 0, "humedad_max": 100,
        "historias": [
            "Te sientas en una duna a descansar.",
            "Una suave brisa de arena te relaja.",
            "Encuentras la sombra de un cactus y recuperas el aliento.",
            "Miras un espejismo a lo lejos y sonríes."
        ],
        "pokemones": [
            {"nombre": "Sandshrew", "tipo": "Tierra", "hp_max": 50, "hp": 50, "prob_captura": 0.50, "disponibles": 3, "ataques": [("Arañazo", 10), ("Excavar", 20)]},
            {"nombre": "Vulpix", "tipo": "Fuego", "hp_max": 45, "hp": 45, "prob_captura": 0.40, "disponibles": 2, "ataques": [("Ascuas", 12), ("Lanzallamas", 20)]},
            {"nombre": "Cacnea", "tipo": "Planta", "hp_max": 50, "hp": 50, "prob_captura": 0.25, "disponibles": 1, "ataques": [("Pin Misil", 12), ("Latigazo", 18)]}
        ]
    },
    {
        "nombre": "Cueva",
        "temp_min": 0, "temp_max": 18,
        "humedad_min": 0, "humedad_max": 100,
        "historias": [
            "El eco de la cueva es tranquilizador.",
            "Te apoyas en una roca y descansas.",
            "Las gotas que caen del techo forman una melodía suave.",
            "Cristales brillantes iluminan tu descanso."
        ],
        "pokemones": [
            {"nombre": "Geodude", "tipo": "Roca", "hp_max": 55, "hp": 55, "prob_captura": 0.50, "disponibles": 3, "ataques": [("Placaje", 10), ("Lanzarrocas", 18)]},
            {"nombre": "Zubat", "tipo": "Veneno", "hp_max": 40, "hp": 40, "prob_captura": 0.45, "disponibles": 2, "ataques": [("Picotazo Veneno", 10), ("Mordisco", 15)]},
            {"nombre": "Onix", "tipo": "Roca", "hp_max": 70, "hp": 70, "prob_captura": 0.25, "disponibles": 1, "ataques": [("Placaje", 10), ("Roca Afilada", 18)]}
        ]
    },
    {
        "nombre": "Playa",
        "temp_min": 12, "temp_max": 40,
        "humedad_min": 60, "humedad_max": 100,
        "historias": [
            "Escuchas las olas romper.",
            "El sonido del mar te invita a cerrar los ojos.",
            "Caminas descalzo por la orilla y te refrescas.",
            "Ves las gaviotas volar sobre el horizonte."
        ],
        "pokemones": [
            {"nombre": "Krabby", "tipo": "Agua", "hp_max": 45, "hp": 45, "prob_captura": 0.50, "disponibles": 3, "ataques": [("Burbuja", 10), ("Pinza", 16)]},
            {"nombre": "Staryu", "tipo": "Agua", "hp_max": 50, "hp": 50, "prob_captura": 0.40, "disponibles": 2, "ataques": [("Pistola Agua", 12), ("Hidropulso", 16)]},
            {"nombre": "Lapras", "tipo": "Agua", "hp_max": 95, "hp": 95, "prob_captura": 0.30, "disponibles": 1, "ataques": [("Pistola Agua", 12), ("Rayo Hielo", 20)]}
        ]
    },
    {
        "nombre": "Pradera",
        "temp_min": 10, "temp_max": 35,
        "humedad_min": 0, "humedad_max": 65,
        "historias": [
            "Te recuestas en el pasto alto.",
            "El viento sopla suavemente.",
            "Observas las nubes pasar mientras descansas.",
            "Un campo de flores te regala un momento de calma."
        ],
        "pokemones": [
            {"nombre": "Pikachu", "tipo": "Eléctrico", "hp_max": 55, "hp": 55, "prob_captura": 0.50, "disponibles": 3, "ataques": [("Impactrueno", 15), ("Ataque Rápido", 10)]},
            {"nombre": "Growlithe", "tipo": "Fuego", "hp_max": 55, "hp": 55, "prob_captura": 0.40, "disponibles": 2, "ataques": [("Ascuas", 12), ("Mordisco", 14)]},
            {"nombre": "Bulbasaur", "tipo": "Planta", "hp_max": 55, "hp": 55, "prob_captura": 0.25, "disponibles": 1, "ataques": [("Látigo Cepa", 12), ("Hoja Afilada", 18)]}
        ]
    }
]

# Le agregamos a cada Pokémon el nombre de su hábitat (dato pedido en el Ítem 1.1)
for hab in habitats:
    for poke in hab["pokemones"]:
        poke["habitat"] = hab["nombre"]

# =========================================================
# FUNCIONES DE APOYO
# =========================================================

def limpiar_pantalla():
    os.system('clear')


def poblacion_total(habitat):
    total = 0
    for poke in habitat["pokemones"]:
        total = total + poke["disponibles"]
    return total


def texto_pokemon(poke):
    # Texto corto para mostrar un Pokémon del equipo
    return f"{poke['nombre']} ({poke['tipo']}) HP {poke['hp']}/{poke['hp_max']}"


def emitir_sonido(nombre):
    # Reproduce la lista de notas del sonido pedido
    try:
        for frecuencia, duracion in SONIDOS[nombre]:
            if frecuencia == 0:
                buzzer.stop()
            else:
                buzzer.play(Tone(frecuencia))
            time.sleep(duracion)
        buzzer.stop()
    except Exception:
        pass   # si el buzzer falla, el juego sigue funcionando


def senalizar(color, sonido):
    # Enciende el LED RGB 2 con un color y reproduce un sonido.
    # El LED queda encendido: quien llama debe apagarlo con led_rgb.off()
    led_rgb.color = color
    emitir_sonido(sonido)


def actualizar_led_poblacion(habitat):
    # LED RGB 1: verde si quedan Pokémon en el hábitat, rojo si está agotado
    if poblacion_total(habitat) > 0:
        led_disp.color = COLOR_HAY_POKEMON
    else:
        led_disp.color = COLOR_AGOTADO

# =========================================================
# LECTURA DE SENSORES Y JOYSTICK
# =========================================================

def leer_joystick():
    x = eje_x.value
    y = eje_y.value
    if y > 20000: return "ABAJO"
    if y < 8000:  return "ARRIBA"
    if x > 20000: return "ENTER"
    if x < 8000:  return "VOLVER"
    return "CENTRO"


def esperar_direccion():
    # Espera a que el joystick vuelva al centro y luego a que se mueva.
    # Así un solo movimiento cuenta como una sola acción.
    while leer_joystick() != "CENTRO":
        time.sleep(0.05)
    while True:
        direccion = leer_joystick()
        if direccion != "CENTRO":
            return direccion
        time.sleep(0.05)


def esperar_volver():
    # Espera hasta que el jugador mueva el joystick a la izquierda
    while True:
        if esperar_direccion() == "VOLVER":
            emitir_sonido("confirmar")
            return


def leer_ambiente():
    for _ in range(3):
        try:
            temp = sensor_dht.temperature
            hum = sensor_dht.humidity
            if temp is not None and hum is not None:
                return temp, hum
        except RuntimeError:
            time.sleep(0.5)
    return 20, 50   # valores por defecto si el sensor falla


def filtrar_habitats(temp, hum):
    disponibles = []
    for hab in habitats:
        temp_ok = hab["temp_min"] <= temp <= hab["temp_max"]
        hum_ok = hab["humedad_min"] <= hum <= hab["humedad_max"]
        if temp_ok and hum_ok:
            disponibles.append(hab)
    return disponibles

# =========================================================
# MENÚ GENÉRICO CON JOYSTICK
# =========================================================

def mostrar_menu(encabezado, opciones, permitir_volver=False, sonar_confirmar=True):
    # Muestra un menú y devuelve el número de la opción elegida.
    # Si permitir_volver es True y el jugador va a la izquierda, devuelve -1.
    seleccion = 0

    while True:
        limpiar_pantalla()
        print(encabezado)
        print()
        for i in range(len(opciones)):
            if i == seleccion:
                print(" -> " + opciones[i])
            else:
                print("    " + opciones[i])
        print()
        if permitir_volver:
            print("(Arriba/Abajo: mover | Derecha: elegir | Izquierda: volver)")
        else:
            print("(Arriba/Abajo: mover | Derecha: elegir)")

        direccion = esperar_direccion()

        if direccion == "ABAJO":
            seleccion = seleccion + 1
            if seleccion >= len(opciones):
                seleccion = 0
            emitir_sonido("navegar")
        elif direccion == "ARRIBA":
            seleccion = seleccion - 1
            if seleccion < 0:
                seleccion = len(opciones) - 1
            emitir_sonido("navegar")
        elif direccion == "ENTER":
            if sonar_confirmar:
                emitir_sonido("confirmar")
            return seleccion
        elif direccion == "VOLVER" and permitir_volver:
            emitir_sonido("confirmar")
            return -1

# =========================================================
# POKÉDEX Y EQUIPO
# =========================================================

def mostrar_ficha(poke):
    limpiar_pantalla()
    print(f"--- POKÉDEX: {poke['nombre'].upper()} ---")
    print(f"Tipo: {poke['tipo']}")
    print(f"Hábitat: {poke['habitat']}")
    print(f"HP máximo: {poke['hp_max']}")
    print(f"Prob. captura: {poke['prob_captura'] * 100:.0f}%")
    print(f"Ejemplares: {poke['disponibles']}")
    print(f"Ataque 1: {poke['ataques'][0][0]} (daño {poke['ataques'][0][1]})")
    print(f"Ataque 2: {poke['ataques'][1][0]} (daño {poke['ataques'][1][1]})")
    print("\n<- Izquierda para volver")
    esperar_volver()


def ver_equipo():
    limpiar_pantalla()
    print("=== MI EQUIPO ===")
    if len(equipo_jugador) == 0:
        print("Todavía no has capturado ningún Pokémon.")
    else:
        for i in range(len(equipo_jugador)):
            print(f" {i + 1}. {texto_pokemon(equipo_jugador[i])}")
    print("\n<- Izquierda para volver")
    esperar_volver()


def ver_pokedex_completa():
    # Muestra todos los hábitats de la base de datos con sus Pokémon (Ítem 1.1)
    limpiar_pantalla()
    print("=== POKÉDEX DEL SAFARI ===")
    for hab in habitats:
        print(f"\n{hab['nombre']} (Temp {hab['temp_min']}-{hab['temp_max']}°C | Hum {hab['humedad_min']}-{hab['humedad_max']}%)")
        for poke in hab["pokemones"]:
            print(f"   - {poke['nombre']} ({poke['tipo']}) - disponibles: {poke['disponibles']}")
    print("\n<- Izquierda para volver")
    esperar_volver()


def elegir_pokemon_equipo(titulo):
    # Devuelve la posición (índice) del Pokémon elegido dentro del equipo
    opciones = []
    for poke in equipo_jugador:
        opciones.append(texto_pokemon(poke))
    return mostrar_menu(titulo, opciones)

# =========================================================
# EVENTO: DESCANSAR (Ítem 1.3)
# =========================================================

def descansar(habitat):
    limpiar_pantalla()
    print("=== DESCANSAR ===")
    print(random.choice(habitat["historias"]))

    # [MEJORA] Descansar recupera un poco de vida al equipo
    if len(equipo_jugador) > 0:
        for poke in equipo_jugador:
            poke["hp"] = poke["hp"] + CURACION_DESCANSO
            if poke["hp"] > poke["hp_max"]:
                poke["hp"] = poke["hp_max"]
        print(f"\nTu equipo recuperó {CURACION_DESCANSO} HP.")

    print("\n<- Izquierda para volver")
    esperar_volver()

# =========================================================
# EVENTO: ATRAPAR (Ítem 1.3)
# =========================================================

def encuentro_captura(poke):
    probabilidad = poke["prob_captura"]
    opciones = ["Lanzar Poké Ball", "Dar de comer", "Escapar"]

    limpiar_pantalla()
    print(f"¡Un {poke['nombre']} salvaje apareció!")
    emitir_sonido("aparicion")
    time.sleep(0.5)

    while True:
        encabezado = (f"¡Un {poke['nombre']} salvaje apareció!\n"
                      f"Probabilidad de captura: {probabilidad * 100:.0f}%")
        eleccion = mostrar_menu(encabezado, opciones, False, False)

        if eleccion == 0:
            # ----- Lanzar Poké Ball -----
            if len(equipo_jugador) >= MAX_EQUIPO:
                limpiar_pantalla()
                print("Tu equipo está lleno (6/6).")
                print("No puedes capturar más con la Poké Ball.")
                print("Gana un combate para poder liberar y capturar.")
                time.sleep(3)
            else:
                limpiar_pantalla()
                print("¡Lanzaste una Poké Ball!")
                time.sleep(1)

                if random.random() <= probabilidad:
                    poke["disponibles"] = poke["disponibles"] - 1
                    nuevo = poke.copy()
                    nuevo["hp"] = nuevo["hp_max"]
                    equipo_jugador.append(nuevo)
                    print(f"¡{poke['nombre']} capturado!")
                    senalizar(VERDE, "exito")
                else:
                    print("¡El Pokémon escapó de la ball!")
                    senalizar(ROJO, "fallo")

                time.sleep(2)
                led_rgb.off()
                return

        elif eleccion == 1:
            # ----- Dar de comer -----
            probabilidad = probabilidad + AUMENTO_COMIDA
            if probabilidad > 1:
                probabilidad = 1
            limpiar_pantalla()
            print("Lanzaste comida...")
            print(f"¡{poke['nombre']} se ve más tranquilo!")
            senalizar(CELESTE, "comida")
            time.sleep(1.5)
            led_rgb.off()

        else:
            # ----- Escapar -----
            limpiar_pantalla()
            print("Escapaste sin problemas.")
            senalizar(AZUL, "escape")
            time.sleep(1.5)
            led_rgb.off()
            return

# =========================================================
# EVENTO: COMBATIR (Ítem 1.4)
# =========================================================

def calcular_multiplicador(tipo_atacante, tipo_defensor):
    if (tipo_atacante, tipo_defensor) in EFECTIVIDAD:
        return EFECTIVIDAD[(tipo_atacante, tipo_defensor)]
    return 1


def atacar(atacante, defensor, ataque):
    # Aplica un ataque, descuenta vida y muestra el resultado
    nombre_ataque = ataque[0]
    danio_base = ataque[1]
    multiplicador = calcular_multiplicador(atacante["tipo"], defensor["tipo"])
    danio = int(danio_base * multiplicador)

    defensor["hp"] = defensor["hp"] - danio
    if defensor["hp"] < 0:
        defensor["hp"] = 0

    limpiar_pantalla()
    print(f"¡{atacante['nombre']} usó {nombre_ataque}!")
    if multiplicador == 2:
        print("¡Es súper efectivo!")
        senalizar(BLANCO, "efectivo")
    elif multiplicador == 0.5:
        print("No es muy efectivo...")
    print(f"{defensor['nombre']} recibió {danio} de daño (HP {defensor['hp']}/{defensor['hp_max']}).")
    time.sleep(2)
    led_rgb.off()


def cerrar_combate_ganado(salvaje):
    # Después de ganar: capturar (o liberar y capturar) o retirarse
    if len(equipo_jugador) < MAX_EQUIPO:
        opciones = ["Capturar", "Retirarse"]
    else:
        opciones = ["Liberar y capturar", "Retirarse"]

    eleccion = mostrar_menu(f"Derrotaste a {salvaje['nombre']}. ¿Qué quieres hacer?", opciones)

    if eleccion != 0:
        limpiar_pantalla()
        print("Te retiras del combate.")
        time.sleep(1.5)
        return

    # Si el equipo está lleno, hay que liberar a alguien primero
    if len(equipo_jugador) >= MAX_EQUIPO:
        indice = elegir_pokemon_equipo("Tu equipo está lleno. ¿Qué Pokémon liberas?")
        liberado = equipo_jugador.pop(indice)
        limpiar_pantalla()
        print(f"Liberaste a {liberado['nombre']}.")
        time.sleep(1.5)

    # La población ya bajó cuando el salvaje fue debilitado, no se descuenta otra vez
    nuevo = salvaje.copy()
    nuevo["hp"] = nuevo["hp_max"]
    equipo_jugador.append(nuevo)

    limpiar_pantalla()
    print(f"¡{nuevo['nombre']} se unió a tu equipo!")
    senalizar(VERDE, "captura_combate")
    time.sleep(2)
    led_rgb.off()


def combate(especie):
    # Devuelve True si el jugador pierde (todos sus Pokémon debilitados)
    salvaje = especie.copy()
    salvaje["hp"] = salvaje["hp_max"]

    limpiar_pantalla()
    print(f"¡Un {salvaje['nombre']} salvaje quiere combatir!")
    emitir_sonido("aparicion")
    time.sleep(1)

    indice = elegir_pokemon_equipo("Elige a tu Pokémon para el combate:")

    while True:
        activo = equipo_jugador[indice]

        encabezado = ("=== COMBATE ===\n"
                      f"Salvaje: {salvaje['nombre']} ({salvaje['tipo']}) HP {salvaje['hp']}/{salvaje['hp_max']}\n"
                      f"Tu Pokémon: {activo['nombre']} ({activo['tipo']}) HP {activo['hp']}/{activo['hp_max']}\n\n"
                      "Elige un ataque:")
        opciones = []
        for ataque in activo["ataques"]:
            opciones.append(f"{ataque[0]} (daño base {ataque[1]})")

        eleccion = mostrar_menu(encabezado, opciones)

        # ----- Turno del jugador -----
        atacar(activo, salvaje, activo["ataques"][eleccion])

        if salvaje["hp"] <= 0:
            especie["disponibles"] = especie["disponibles"] - 1
            limpiar_pantalla()
            print(f"¡{salvaje['nombre']} salvaje fue debilitado!")
            print("¡Ganaste el combate!")
            senalizar(AMARILLO, "victoria")
            time.sleep(2)
            led_rgb.off()
            cerrar_combate_ganado(salvaje)
            return False

        # ----- Turno del Pokémon salvaje (ataque al azar) -----
        ataque_salvaje = random.choice(salvaje["ataques"])
        atacar(salvaje, activo, ataque_salvaje)

        if activo["hp"] <= 0:
            limpiar_pantalla()
            print(f"¡{activo['nombre']} se debilitó!")
            print("Sale del equipo para siempre.")
            senalizar(MORADO, "debilitado")
            time.sleep(2)
            led_rgb.off()
            equipo_jugador.pop(indice)

            if len(equipo_jugador) == 0:
                limpiar_pantalla()
                print("Todos tus Pokémon fueron debilitados.")
                print("Perdiste el combate. Vuelves al menú de hábitats.")
                senalizar(ROJO, "derrota")
                time.sleep(2.5)
                led_rgb.off()
                return True

            indice = elegir_pokemon_equipo("Elige a tu siguiente Pokémon:")

# =========================================================
# PRÓXIMA AVENTURA (Ítems 1.3 y 1.4)
# =========================================================

def proxima_aventura(habitat):
    # Elige un evento al azar. Devuelve True si el jugador perdió un combate.
    eventos = ["Descansar", "Atrapar"]
    if len(equipo_jugador) > 0:
        eventos.append("Combatir")   # solo si ya tiene al menos un Pokémon
    evento = random.choice(eventos)

    # Pokémon del hábitat que todavía tienen ejemplares
    disponibles = []
    for poke in habitat["pokemones"]:
        if poke["disponibles"] > 0:
            disponibles.append(poke)

    if evento == "Descansar":
        descansar(habitat)
    elif len(disponibles) == 0:
        limpiar_pantalla()
        print("No quedan Pokémon aquí.")
        print("\n<- Izquierda para volver")
        esperar_volver()
    elif evento == "Atrapar":
        encuentro_captura(random.choice(disponibles))
    else:
        return combate(random.choice(disponibles))

    return False

# =========================================================
# MENÚS PRINCIPALES
# =========================================================

def menu_habitats():
    # Devuelve el hábitat elegido, o None si el jugador quiere salir
    temp, hum = leer_ambiente()
    habs_disp = filtrar_habitats(temp, hum)

    while True:
        encabezado = ("=== ZONA SAFARI POKÉMON ===\n"
                      f"Clima actual: {temp}°C | Humedad: {hum}%\n"
                      f"Equipo: {len(equipo_jugador)}/{MAX_EQUIPO} Pokémon\n")
        if len(habs_disp) == 0:
            encabezado = encabezado + "\nEl clima actual no permite visitar ningún hábitat."
        else:
            encabezado = encabezado + "\nHábitats que puedes visitar:"

        opciones = []
        for hab in habs_disp:
            if poblacion_total(hab) > 0:
                estado = "OK"
            else:
                estado = "AGOTADO"
            opciones.append(f"{hab['nombre']} - {estado}")
        opciones.append("Ver mi equipo")
        opciones.append("Ver Pokédex del Safari")

        eleccion = mostrar_menu(encabezado, opciones, True)

        if eleccion == -1:
            return None
        elif eleccion < len(habs_disp):
            return habs_disp[eleccion]
        elif eleccion == len(habs_disp):
            ver_equipo()
        else:
            ver_pokedex_completa()


def menu_pokemones(habitat):
    while True:
        # LED RGB 1: verde si quedan Pokémon, rojo si el hábitat está agotado
        actualizar_led_poblacion(habitat)

        encabezado = (f"=== HÁBITAT: {habitat['nombre'].upper()} ===\n"
                      f"Población restante: {poblacion_total(habitat)}\n"
                      f"Equipo: {len(equipo_jugador)}/{MAX_EQUIPO} Pokémon")

        # La primera opción es la aventura, las demás son los Pokémon del hábitat
        opciones = ["¡BUSCAR PRÓXIMA AVENTURA!"]
        for poke in habitat["pokemones"]:
            if poke["disponibles"] > 0:
                estado = f"{poke['disponibles']} disp."
            else:
                estado = "AGOTADO"
            opciones.append(f"{poke['nombre']} ({poke['tipo']}) - [{estado}]")

        eleccion = mostrar_menu(encabezado, opciones, True)

        if eleccion == -1:
            led_disp.off()
            return
        elif eleccion == 0:
            perdio = proxima_aventura(habitat)
            if perdio:
                # Derrota: vuelve al menú de hábitats
                led_disp.off()
                return
        else:
            mostrar_ficha(habitat["pokemones"][eleccion - 1])

# =========================================================
# PROGRAMA PRINCIPAL
# =========================================================

def main():
    led_disp.off()
    led_rgb.off()

    try:
        while True:
            habitat_elegido = menu_habitats()
            if habitat_elegido is None:
                limpiar_pantalla()
                print("¡Hasta pronto!")
                print(f"Te llevaste {len(equipo_jugador)} Pokémon.")
                break
            menu_pokemones(habitat_elegido)

    except KeyboardInterrupt:
        print("\nCerrando programa...")
    finally:
        led_disp.off()
        led_rgb.off()
        buzzer.stop()
        sensor_dht.exit()


if __name__ == "__main__":
    main()
