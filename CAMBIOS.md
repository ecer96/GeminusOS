# GeminusOS — Registro de cambios

Launcher propio para la Anbernic RG DS Plus (RK3568, doble pantalla 1024x768).
Sustituye al launcher oficial `dmenu.bin` (58% CPU en reposo -> 0% actual).

Ultima actualizacion: v1.25 — logros locales de NDS, escaneo automatico/manual y recomendaciones en la pantalla superior.

---

## Estructura del proyecto

~/Escritorio/GeminusOS/
├── ecerlauncher/
│   ├── src/
│   │   ├── main.c                Bucle principal, 2 ventanas SDL, vistas
│   │   ├── input.c / input.h     /dev/input (D-pad, botones, touch)
│   │   ├── launch.c / launch.h   fork+execv de emuladores
│   │   ├── platforms.c / .h      Tabla de plataformas
│   │   ├── roms.c / roms.h       Escaneo de ROMs (dinamico)
│   │   ├── scan.c / scan.h       Contador de ROMs por plataforma
│   │   ├── ui_grid.c / ui_grid.h Grid 3x4 de plataformas
│   │   ├── ui_slider.c / .h      Carrusel de juegos
│   │   ├── ui_menu.c / ui_menu.h Menu de ajustes
│   │   ├── art.c / art.h         Carga de caratulas (stb_image)
│   │   ├── text.c / text.h       Cache de texturas de texto
│   │   ├── status.c / status.h   Hora, bateria, WiFi
│   │   ├── stb_image.h           (terceros, header unico)
│   │   └── stb_image_resize2.h   (terceros, header unico)
│   ├── build/
│   │   └── ecerlauncher          binario ARM aarch64
│   ├── build.sh                  compilacion cruzada con clang
│   └── ecerlauncher-BACKUP-*/    backups con fecha
└── backup-consola/               backups de la consola
    ├── ctrl/ bin/ init.d/

---

## Estado actual de componentes

| Componente | Estado | Notas |
|---|---|---|
| Arranque automatico | OK | via loadapp.sh -> ecerlauncher |
| Grid de plataformas | OK | 3 columnas, scroll, marquee |
| Foco superior (Buscar/Menu) | OK | navegable con D-pad y touch |
| Slider de juegos | OK | 5 cartas visibles, arcoiris, dots |
| Menu de ajustes | OK | 8 items, touch funcional, 4% CPU |
| D-pad + botones | OK | lee /dev/input/event5 |
| Touch | OK | cola TE_DOWN/MOVE/UP, gestos |
| Doble pantalla | OK | SDL_DOUBLE_BUFFER por ventana |
| Lanzar emuladores | OK | sin bloquear, _exit inmediato |
| Relanzado post-juego | OK | ndsCtrl-libdsflip.sh v36 |
| WiFi no se cae | OK | no matamos loadapp.sh |
| Caratulas | OK | fit + fill con stb_image |
| Cache de texto | OK | FNV-1a, 96 entradas |
| Barra de estado | OK | hora + bateria + icono WiFi de barras |
| RAM | OK | ~62 MB VmRSS (de 953 MB) |
| CPU en reposo (grid) | OK | 0% |
| CPU en menu abierto | OK | 4% (antes 18%) |
| Titulo superior largo | OK | marquee horizontal |
| Toggles REALES | PENDIENTE | aplicar a WiFi/SSH/MTP/Brillo/Volumen |
| Persistencia | PENDIENTE | guardar toggles entre reinicios |

---

## Menu de ajustes

### Items

| Item | Estado | Accion actual |
|---|---|---|
| WiFi | Placeholder | Cambia estado visual (no aplica a nmcli) |
| SSH | Placeholder | Cambia estado visual (no arranca/para sshd) |
| MTP | Placeholder | Cambia estado visual (no arranca/para umtprd) |
| Brillo | Placeholder | Ajusta valor 0-100 (no escribe a /sys/...) |
| Volumen | Placeholder | Ajusta valor 0-100 (no llama a amixer) |
| Info | Placeholder | Muestra datos ficticios |
| Reiniciar | OK | sync() + reboot(RB_AUTOBOOT) |
| Apagar | OK | sync() + reboot(RB_POWER_OFF) |

### Navegacion

Con D-pad:
- Arriba/Abajo: mover seleccion
- Izq/Der: ajustar brillo/volumen (solo en esas tarjetas)
- A: activar (toggle, abrir info, confirmar)
- B: cerrar menu (o cancelar confirmacion)

Con touch:
- Tap en tarjeta NO seleccionada -> la selecciona
- Tap en tarjeta YA seleccionada -> la activa
- Tap en "Volver" -> cierra
- Tap en "Si" (mitad superior del dialogo) -> confirma reinicio/apagado
- Tap en "No" (mitad inferior) -> cancela

### Como se abre

- Touch en "Menu" (arriba a la derecha del grid de plataformas)
- D-pad: subir desde la primera fila del grid -> foco a "Buscar" -> derecha -> "Menu" -> A

### Como se cierra

- Touch en "Volver"
- Boton B fisico
- Boton MENU fisico (no-op, no cierra)

### Optimizacion

- menu_dirty: solo redibuja cuando hay interaccion (antes: cada vuelta del bucle)
- input_wait(30) antes de input_poll(): no gira en vacio
- Resultado: 4% CPU con el menu abierto (antes 18%)

---

## Dispositivos de entrada confirmados

| Device | Nombre | Uso |
|---|---|---|
| /dev/input/event0 | rk805 pwrkey | Boton de encendido |
| /dev/input/event1 | gt9xx-0 | Touch (Goodix GT9xx) |
| /dev/input/event5 | ANBERNIC-rk3568-keys | D-pad + botones |

### Codigos del D-pad (event5, EV_ABS)
| Accion | Code | Value |
|---|---|---|
| Arriba | 0x11 (Y) | -1 |
| Abajo | 0x11 | +1 |
| Izquierda | 0x10 (X) | -1 |
| Derecha | 0x10 | +1 |

### Codigos de botones (event5, EV_KEY)
| Boton | Code |
|---|---|
| A | 0x130 |
| B | 0x131 |
| Y | 0x132 |
| X | 0x133 |
| SELECT | 0x136 |
| START | 0x137 |
| MENU (no existe fisicamente) | 0x138 |

### Touch (event1, multitouch tipo B)
| Evento | Code | Notas |
|---|---|---|
| ABS_MT_TRACKING_ID | 0x39 | 0=down, -1=up |
| ABS_MT_POSITION_X | 0x35 | X crudo (0-1023) |
| ABS_MT_POSITION_Y | 0x36 | Y crudo (0-767) |
| ABS_MT_TOUCH_MAJOR | 0x30 | ignorado |
| ABS_MT_TOUCH_MINOR | 0x32 | ignorado |
| ABS_MT_SLOT | 0x2f | ignorado >0 |
| BTN_TOUCH | 0x14a | no siempre se emite |
| SYN_REPORT | -- | fin de frame |

### Calibracion del touch pendiente

Las coordenadas que reporta el panel tactil estan desplazadas respecto a la pantalla.
Al tocar "WiFi" en el menu (visualmente en Y=90-162), el touch reporta Y~289-303.

Offset medido empiricamente (aproximado):
- X: ~90 px
- Y: ~170 px

Se puede sobrescribir en tiempo de ejecucion con ECER_TOUCH_OFFX y ECER_TOUCH_OFFY.
Aun no aplicado en input.c.

---

## Rutas del sistema leidas

### Bateria
- /sys/class/power_supply/cw2015-battery/capacity -> % (entero)
- /sys/class/power_supply/cw2015-battery/status -> Charging / Discharging / Full

### WiFi
- /proc/net/wireless -> linea wlan0: con link/level
- nmcli -t -f ACTIVE,SSID,SIGNAL dev wifi -> yes:SSID:SIGNAL

### Sistema
- /sys/class/thermal/thermal_zone0/temp -> temperatura (/1000 = C)
- /sys/class/net/wlan0/address -> MAC
- /proc/version -> kernel
- /proc/uptime -> uptime

### Brillo (pendiente)
- /sys/class/backlight/backlight/brightness (90/255 actual)
- /sys/class/backlight/backlight1/brightness (90/255 actual)
- /mnt/vendor/bin/bright.dge

### Volumen (pendiente)
- amixer set Master N% (0-100)
- tinymix set <num> <val>
- pactl set-sink-volume

### WiFi/SSH/MTP (pendiente)
- WiFi: nmcli radio wifi on/off
- SSH: /etc/init.d/S50sshd start/stop
- MTP: umtprd (binario en /usr/bin/umtprd)

---

## Integracion en la consola

### Arranque
S60launch (init) -> loadapp.sh -> ecerlauncher (bucle infinito)

### Al lanzar un juego
ecerlauncher -> fork+execv -> ndsCtrl-libdsflip.sh <rom> -> DraStic
                    |
              _exit(0) / running = 0
                    |
           (launcher se cierra)

Al salir de DraStic:
ndsCtrl-libdsflip.sh -> relanza ecerlauncher (nohup)

### Launchers en la consola
| Launcher | Estado |
|---|---|
| ecerlauncher | En uso |
| dmenu.bin | Deshabilitado (.disabled) |
| dmenu_ln | Deshabilitado |
| menu-drastic | Menu interno DraStic |

---

## Reglas aprendidas

1. Nunca matar loadapp.sh -> tira el WiFi 30 s. El wrapper v36 ya no lo mata.
2. Renombrar != borrar -> siempre reversible.
3. Backup antes de editar main.c -> se nos corrompio una vez.
4. No compilar a ciegas -> verificar rutas en la consola antes.
5. Medir antes de optimizar: la consola tiene 953 MB de RAM. 62 MB es 6.5%.
6. SDL_Delay en el menu es malo: anade latencia al touch. Usar input_wait(timeout).
7. menu_dirty: solo redibujar cuando hay interaccion.

---

## Pendiente / ideas para siguientes fases

### Inmediato
- [ ] Implementar toggles REALES (WiFi, SSH, MTP, Brillo, Volumen)
- [ ] Aplicar offset de calibracion del touch en input.c
- [ ] Persistir estado del menu en /mnt/data/ecer_config.ini

### Corto plazo
- [ ] Barra de estado: temperatura, hora con segundos
- [ ] Pantalla de busqueda (ya hay boton "Buscar")
- [ ] Cola de botones (ahora se pierde un boton si se pulsan 2 seguidos)

### Medio plazo
- [ ] Caratulas: buscar en mas rutas / mas formatos
- [ ] Historial "Recientes" (ultimos 20 juegos)
- [ ] Favoritos (marcar con Y)

### Largo plazo
- [ ] Scraper (bajar caratulas de ScreenScraper / TheGamesDB)
- [ ] Ajustes por juego (shaders, frameskip)
- [ ] Modo TV (HDMI out)

---

## Backups

### En el PC
- ~/Escritorio/GeminusOS/ecerlauncher-BACKUP-*/ (con fecha)

### En la consola
- /mnt/vendor/ctrl/loadapp.sh.pre-ecerlauncher.bak
- /mnt/vendor/ctrl/ndsCtrl-libdsflip.sh.pre-v36.bak
- /mnt/vendor/ctrl/menu-drastic.pre-v12_1.bak
- /mnt/vendor/bin/dmenu.bin.disabled

---

## Comandos habituales

### Compilar
cd ~/Escritorio/GeminusOS/ecerlauncher
bash build.sh

### Subir a la consola (con contrasena automatica)
export SSHPASS='rocknix'
cd ~/Escritorio/GeminusOS/ecerlauncher
sshpass -e ssh -o StrictHostKeyChecking=no root@192.168.1.36 'pkill -9 -x ecerlauncher; sleep 1'
sshpass -e scp -o StrictHostKeyChecking=no build/ecerlauncher root@192.168.1.36:/mnt/vendor/ctrl/ecerlauncher
sshpass -e ssh -o StrictHostKeyChecking=no root@192.168.1.36 'chmod +x /mnt/vendor/ctrl/ecerlauncher; sync'
sshpass -e ssh -o StrictHostKeyChecking=no root@192.168.1.36 'nohup /mnt/vendor/ctrl/ecerlauncher > /tmp/ecerlauncher.log 2>&1 & sleep 2; pgrep -x ecerlauncher'

### Ver el log
sshpass -e ssh -o StrictHostKeyChecking=no root@192.168.1.36 'cat /tmp/ecerlauncher.log'

### Medir CPU en vivo
sshpass -e ssh -o StrictHostKeyChecking=no root@192.168.1.36 'PID=$(pgrep -x ecerlauncher); read u1 s1 < <(awk "{print \$14,\$15}" /proc/$PID/stat); sleep 5; read u2 s2 < <(awk "{print \$14,\$15}" /proc/$PID/stat); echo "CPU: $(( ((u2-u1)+(s2-s1)) * 100 / 500 ))%"'

### Medir RAM
sshpass -e ssh -o StrictHostKeyChecking=no root@192.168.1.36 'grep VmRSS /proc/$(pgrep -x ecerlauncher)/status'

### Touch en vivo (ver eventos)
sshpass -e ssh -o StrictHostKeyChecking=no root@192.168.1.36 'timeout 5 cat /dev/input/event1 | xxd'

### Backup del launcher actual
BACKUP=~/Escritorio/GeminusOS/ecerlauncher-BACKUP-$(date +%Y%m%d-%H%M%S)
mkdir -p "$BACKUP"
cp -r ~/Escritorio/GeminusOS/ecerlauncher/src "$BACKUP/"
cp -r ~/Escritorio/GeminusOS/ecerlauncher/build "$BACKUP/"
cp    ~/Escritorio/GeminusOS/ecerlauncher/build.sh "$BACKUP/"
echo "Backup en $BACKUP"

---

## Proximos pasos

1. Toggles reales - que WiFi/SSH/MTP/Brillo/Volumen cambien el sistema
2. Persistencia - guardar estado en /mnt/data/ecer_config.ini
3. Calibracion touch - aplicar offset 90/170 en input.c
4. Info real - leer IP, MAC, kernel, temperatura en vivo
