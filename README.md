# GeminusOS

Sistema operativo listo para usar en la **Anbernic RG DS Plus** (Rockchip
RK3568, doble pantalla de 1024×768). Incluye launcher propio, emuladores,
menú in-game, aplicaciones y ajustes del sistema en una sola imagen.

![GeminusOS](https://img.shields.io/badge/versi%C3%B3n-v1.2-blue)

## Descarga

La imagen está en **[la release v1](https://github.com/ecer96/GeminusOS/releases/tag/v1)**:

| Archivo | Tamaño | SHA-256 |
|---|---|---|
| `GeminusOS-v1.1.img.zst` | 1,7 GB | `40bcf0d689fc9c35124b1946469c5e688d665a1e5d5da5995d16ca784ab08674` |

La imagen descomprimida ocupa 15,5 GB. Necesitas una microSD de **16 GB como
mínimo** (se recomienda 32 GB).

## Instalación

1. Descarga `GeminusOS-v1.1.img.zst`.
2. Verifica el SHA-256:

   ```bash
   sha256sum GeminusOS-v1.img.zst
   ```

3. Descomprime:

   ```bash
   zstd -d GeminusOS-v1.img.zst
   ```

   También puedes usar 7-Zip (con soporte Zstandard) o `unzstd`.

4. Flashea `GeminusOS-v1.img` en la microSD con **balenaEtcher**, **Rufus** o:

   ```bash
   sudo dd if=GeminusOS-v1.img of=/dev/sdX bs=4M status=progress conv=fsync
   ```

   > Sustituye `/dev/sdX` por tu tarjeta. **Se borrará todo su contenido.**

5. Inserta la tarjeta en la consola y enciéndela.

## Qué incluye

### Interfaz

- Launcher propio con **tres vistas de inicio**: cuadrícula, panel + lista y
  carrusel tipo consola.
- **Tres vistas de juegos**: slider clásico, rueda y cuadrícula.
- Carátulas, sinopsis y metadatos de los juegos.
- Pantalla superior con carátula, información del juego, logros y estado del
  sistema.
- Navegación completa con D-pad, botones y pantalla táctil.
- Temas claro/oscuro, color de acento personalizable e interfaz en **español e
  inglés**.

### Biblioteca

- Escaneo automático de ROMs por plataforma.
- **Favoritos**, **Recientes**, **Con logros** y **Sin carátula**.
- Búsqueda con teclado en pantalla.
- Ordenación y juego aleatorio (“Sorpresa”).
- **Scraping** de carátulas y datos con Libretro o ScreenScraper.
- **RetroAchievements**: progreso, logros, insignias y sincronización.

### Durante el juego

- **Panel in-game** en la pantalla inferior para RetroArch:
  - Guardar y cargar estado.
  - Fast forward, pausa, reset y menú de RetroArch.
  - Captura de pantalla.
  - Brillo y volumen.
  - Temperatura, CPU, RAM y batería en tiempo real.
- **Nintendo DS** con DraStic:
  - Menú in-game propio.
  - Shaders personalizados (`.dfx`, `.dsd`, `.frag`).
  - Guardar/cargar estado, fast forward, micrófono y captura.
- Guardado automático y “Continuar” para retomar la última partida.

### Aplicaciones

- **Navegador** web ligero.
- **YouTube**.
- **Reproductor multimedia**.
- **Ports** y aplicaciones adicionales desde la carpeta `APPS`.

### Sistema

- WiFi, SSH y MTP.
- Brillo, volumen y apagado automático de pantalla.
- Fecha y hora.
- Información del sistema: IP, MAC, kernel, temperatura, CPU, RAM y batería.
- Reinicio y apagado seguro.

### Rendimiento

Diseñado para la RG DS Plus: **0 % de CPU en reposo** y alrededor de **62 MB de
RAM**, con redibujado solo cuando hay cambios.

## Plataformas compatibles

**Emuladores dedicados**

Nintendo DS · PSP · Dreamcast · Saturn · OpenBOR · Pico-8

**RetroArch**

Game Boy · Game Boy Color · Game Boy Advance · NES · SNES · Sega Genesis /
Mega Drive · Sega CD · Sega 32X · Master System · Game Gear · Nintendo 64 ·
PlayStation · Atari 2600 · Atari 5200 · Atari 7800 · Atari 800 · Atari Lynx ·
Atari ST · Commodore 64 · VIC-20 · Amiga · CPS1 · CPS2 · CPS3 · Neo Geo ·
Neo Geo CD · Neo Geo Pocket · MAME · FBNeo · MSX · PC Engine · PC Engine CD ·
WonderSwan · Virtual Boy · Pokemon Mini · Game & Watch · ScummVM · DOS ·
EasyRPG · ONS

**Otros**

Ports · Apps

## ROMs y contenido

Coloca tus juegos en la microSD:

```
/mnt/sdcard/roms/<sistema>/
```

Por ejemplo:

```
/mnt/sdcard/roms/nds/
/mnt/sdcard/roms/snes/
/mnt/sdcard/roms/psx/
/mnt/sdcard/roms/APPS/
```

Las carátulas y metadatos se pueden descargar desde el menú **Scraper**.
Las BIOS deben colocarse donde las espere cada emulador.

## Controles

| Botón | Acción |
|---|---|
| D-pad / stick | Navegar |
| **A** | Abrir / confirmar |
| **B** | Volver / cancelar |
| **X** | Logros del juego (en la biblioteca) / continuar último juego (en inicio) |
| **Y** | Opciones: favorito, sorpresa, colección, ordenar, scrapear |
| **L1 / R1** | Salto alfabético en la lista de juegos |
| **Select** | Jugar al juego del día |
| **Menu** | Abrir ajustes |
| Táctil | Navegación y acciones |

## Aviso

GeminusOS no incluye juegos, ROMs ni BIOS. Usa únicamente contenido que poseas
legalmente. Los componentes de terceros conservan sus propias licencias.
