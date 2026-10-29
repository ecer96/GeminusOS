# GeminusOS

[English](README.md) | **Español**

Sistema operativo listo para usar en la **Anbernic RG DS Plus** (Rockchip
RK3568, doble pantalla de 1024×768). Incluye launcher propio, emuladores,
menú in-game, aplicaciones y ajustes del sistema en una sola imagen.

![GeminusOS](https://img.shields.io/badge/versi%C3%B3n-v1.34-blue)

## Descarga

La imagen base está en **[la release v1](https://github.com/ecer96/GeminusOS/releases/tag/v1)**:

| Archivo | Tamaño | SHA-256 |
|---|---|---|
| `GeminusOS-v1.1.img.zst` | 1,7 GB | `40bcf0d689fc9c35124b1946469c5e688d665a1e5d5da5995d16ca784ab08674` |

La imagen descomprimida ocupa 15,5 GB. Necesitas una microSD de **16 GB como
mínimo** (se recomienda 32 GB).

> La imagen descargable es la **base v1.1**. Tras el primer arranque, actualiza a
> la última versión (actualmente **v1.34**) desde **Ajustes → Actualizar**. La
> imagen base ya incluye el actualizador.

## Instalación

1. Descarga `GeminusOS-v1.1.img.zst`.
2. Verifica el SHA-256:

   ```bash
   sha256sum GeminusOS-v1.1.img.zst
   ```

3. Descomprime:

   ```bash
   zstd -d GeminusOS-v1.1.img.zst
   ```

   También puedes usar 7-Zip (con soporte Zstandard) o `unzstd`.

4. Flashea `GeminusOS-v1.1.img` en la microSD con **balenaEtcher**, **Rufus** o:

   ```bash
   sudo dd if=GeminusOS-v1.1.img of=/dev/sdX bs=4M status=progress conv=fsync
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

## ROMs, apps y ports

GeminusOS **no** incluye juegos, ROMs ni BIOS.

### Carpetas de ROMs

GeminusOS lee juegos de **las dos microSD**:

| Tarjeta | Ruta | Mayúsculas/minúsculas |
|---|---|---|
| Tarjeta del sistema (donde está flasheado GeminusOS) | `/mnt/mmc/Roms/<SISTEMA>/` | Mayúsculas: `NDS`, `SNES`, `PSX` |
| Segunda tarjeta / externa | `/mnt/sdcard/roms/<sistema>/` | Minúsculas: `nds`, `snes`, `psx` |

La partición de ROMs de la tarjeta del sistema suele aparecer como **ROMS** en el PC; la externa aparece como otra unidad. Puedes usar cualquiera de las dos, o ambas a la vez.

Ejemplos habituales para la **tarjeta externa**:

| Sistema | Carpeta |
|---|---|
| Nintendo DS | `roms/nds/` |
| PSP | `roms/psp/` |
| Dreamcast | `roms/dreamcast/` |
| Saturn | `roms/saturn/` |
| Game Boy / Color / Advance | `roms/gb/`, `roms/gbc/`, `roms/gba/` |
| NES / SNES | `roms/nes/`, `roms/snes/` |
| Genesis / Master System / Game Gear | `roms/genesis/`, `roms/mastersystem/`, `roms/gamegear/` |
| Nintendo 64 | `roms/n64/` |
| PlayStation | `roms/psx/` |
| Arcade | `roms/mame/`, `roms/fbneo/`, `roms/cps1/`, `roms/cps2/`, `roms/cps3/`, `roms/neogeo/` |

Para juegos de varios discos, usa una subcarpeta con una lista `.m3u` cuando el emulador lo admita.

### Apps y ports

| Tipo | Carpeta | Contenido |
|---|---|---|
| **Apps** | `/mnt/sdcard/roms/APPS/` | Scripts `.sh`; uno por aplicación |
| **Ports** | `/mnt/sdcard/roms/ports/` o `/mnt/mmc/Roms/PORTS/` | Lanzadores de ports; un `.sh` por port |

`APPS` va en mayúsculas. Las apps de usuario se leen **solo de la tarjeta externa**: la carpeta `APPS` del firmware en la tarjeta del sistema se ignora a propósito. La carpeta externa ya incluye las apps internas: navegador, YouTube y reproductor multimedia. Añade tus propios `.sh` y aparecerán en la sección **Apps**.

### Copiar archivos desde el PC

- Usa **MTP** desde la consola (Ajustes → MTP), o
- Saca cualquiera de las dos microSD y usa un lector de tarjetas.

En Windows, la partición de ROMs de la tarjeta del sistema puede aparecer como **ROMS**, y la externa como otra unidad. No modifiques las particiones del sistema.

Las carátulas y metadatos se descargan desde el **Scraper** (ver abajo). Las BIOS no están incluidas: colócalas donde las espere cada emulador.

## Logros

### RetroAchievements (RetroArch)

Abre **Ajustes → RetroAchievements**, introduce usuario y contraseña y usa **Sincronizar logros** para actualizar el progreso. Los datos aparecen en el launcher cuando están disponibles. Hace falta conexión a internet.

### Logros locales de Nintendo DS

Los juegos de NDS pueden usar logros evaluados **en la propia consola** mediante DraStic:

- La primera vez que abres un juego de NDS, GeminusOS prepara sus logros automáticamente si hay WiFi y cuenta de RetroAchievements configurada.
- Puedes volver a escanear desde la lista de juegos NDS: **Start → Opciones → Escanear logros de este juego / esta colección / todos**.
- Dentro del juego, pulsa **Menu** y abre la pestaña **Logros**.
- En el launcher, selecciona un juego de NDS y pulsa **X** para ver su lista local.
- Al desbloquear uno aparece un aviso en pantalla con su badge.

Estos logros se guardan y evalúan en local. No se envía ni se concede nada a RetroAchievements. Algunas definiciones complejas de RA pueden no ser compatibles.

## Scrapers

Abre **Ajustes → Scraper** para elegir proveedor y empezar:

| Proveedor | Requisitos |
|---|---|
| **Libretro** | Sin cuenta ni API key |
| **TheGamesDB** | API key gratuita |
| **ScreenScraper** | Usuario y contraseña de ScreenScraper |

Puedes scrapear la plataforma actual o todas desde esa misma pantalla.

Desde la biblioteca también puedes pulsar **Start → Opciones** y elegir:

- **Scrapear este juego**
- **Scrapear esta colección**

Desde la parrilla de plataformas, pulsa **Start** para scrapear la colección actual o todas.

El scraping necesita WiFi. Las carátulas y metadatos se guardan por juego; vuelve a ejecutarlo para refrescar o completar datos.

## Temas, color de acento e idioma

- **Ajustes → Tema** cambia entre los temas claro/oscuro integrados y los temas personalizados.
- Los temas personalizados son archivos `.theme` en:

```text
/mnt/sdcard/GeminusOS/themes/
```

- **Ajustes → Color de acento** cambia el color de resaltado.
- **Ajustes → Idioma** cambia entre español e inglés. El launcher se recarga automáticamente.

### Iconos personalizados del launcher

Puedes sustituir los iconos de plataforma del grid/inicio:

| Tema | Carpeta |
|---|---|
| Tema oscuro | `/mnt/sdcard/GeminusOS/icons/` |
| Tema claro | `/mnt/sdcard/GeminusOS/icons_light/` |

- Usa el nombre que espera la plataforma: `nds.png`, `snes.png`, `ps.png`, `gba.png`, `apps.png`, `ports.png`, etc.
- PNG cuadrado con fondo transparente; se recomienda 256×256.
- Iconos **blancos** para el tema oscuro y **negros** para el claro.
- Los iconos del usuario tienen prioridad sobre los integrados. Reinicia el launcher o cambia de tema para recargarlos.

## Actualizar

Abre **Ajustes → Actualizar**.

- GeminusOS comprueba si hay una versión nueva al arrancar y periódicamente en segundo plano.
- Si hay una versión nueva, el menú la muestra y puedes instalarla con un botón.
- El actualizador descarga el payload, verifica su SHA-256, lo instala y reinicia el launcher.
- **No** hace falta volver a flashear la microSD para las actualizaciones normales.

La imagen base descargable es la v1.1. Tras el primer arranque, actualiza a la última versión (actualmente **v1.29**). Si la comprobación falla, el menú muestra **“Sin conexión / no se pudo comprobar”** en lugar de decir que todo está al día.

## Menús dentro del juego

### RetroArch — panel de la pantalla inferior

Al iniciar un juego de RetroArch, el panel aparece en la pantalla inferior. Toca las pestañas:

- **Control**: fast forward, guardar/cargar estado, captura, pausa, reset, menú de RetroArch y cerrar juego.
- **Pantalla**: brillo, volumen y opciones de pantalla.
- **Sistema**: información del sistema y opciones de energía.

La pantalla superior sigue mostrando el juego.

### DraStic — menú de Nintendo DS

Pulsa el botón **Menu** durante un juego de NDS. El menú aparece en la pantalla inferior:

- **Principal**: fast forward, guardar/cargar estado, micrófono, volumen, cerrar menú y salir del emulador.
- **Opciones**: shaders, sensibilidad del micrófono, resolución 3D, reiniciar, WiFi y escaneo de logros.
- **Apariencia**: tema, color de acento e idioma.
- **Logros**: lista de logros locales del juego actual.

Usa **A** para confirmar, **B** para volver y **Menu** para cerrar. La pantalla superior muestra la barra de estado.

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
