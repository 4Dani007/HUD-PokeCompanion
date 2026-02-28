# HUD PokeCompanion

Aplicacion de escritorio para mostrar en tiempo casi real informacion de un guardado de **Pokemon Ultra Luna** (Azahar/Citra), incluyendo:

- Equipo actual con sprites.
- Ficha detallada tipo Pokedex (stats, tipos, movimientos, debilidades, etc.).
- Cadena de evolucion y condiciones.
- Datos del entrenador.
- Progreso de Pokedex (vistos/capturados) y vista completa filtrable.
- Monitoreo automatico del archivo `main` para refresco en vivo.

## Stack

- **Python** (UI con `tkinter`)
- **Pillow** + **requests**
- **.NET 6** para el wrapper `PokeLastCatch`
- **PKHeX.Core** para parsear el save de Gen 7

## Estructura

- `ui_equipo.py`: UI principal + logica de refresco + PokeAPI.
- `mostrar_equipo.py`: salida en consola (modo simple).
- `PokeLastCatch/Program.cs`: wrapper C# que lee el save y devuelve JSON.
- `PokeLastCatch/PokeLastCatch.csproj`: proyecto .NET.

## Requisitos

1. Python 3.10+ (recomendado).
2. .NET SDK 6 instalado.
3. Dependencias Python:

```bash
pip install requests Pillow
```

## Ruta del save

Por defecto se usa:

`C:\Users\danie\AppData\Roaming\Azahar\sdmc\Nintendo 3DS\00000000000000000000000000000000\00000000000000000000000000000000\title\00040000\001b5100\data\00000001\main`

Si tu ruta cambia, actualiza `RUTA_SAVE` en:

- `ui_equipo.py`
- `mostrar_equipo.py`

## Como ejecutar

### 1) Compilar wrapper C#

```bash
dotnet build .\PokeLastCatch
```

### 2) Ejecutar UI principal

```bash
python .\ui_equipo.py
```

### 3) Ejecutar modo consola (opcional)

```bash
python .\mostrar_equipo.py
```

## Funcionalidades clave

- **Auto-refresh**: detecta cambios del save y vuelve a renderizar.
- **Tarjetas del equipo**: nivel, amistad, evolucion y acceso a ficha.
- **Pokedex completa**:
  - Busqueda por nombre o ID.
  - Filtros por estado (vistos/capturados/no vistos).
  - Doble clic para abrir ficha.
- **Evolucion**:
  - Lee cadena desde PokeAPI.
  - Muestra condicion normalizada (nivel, item, intercambio, amistad, etc.).

## Troubleshooting

- **No se pudo leer save**:
  - Verifica `RUTA_SAVE`.
  - Asegurate de que el archivo exista y no este bloqueado.

- **Error de red/API**:
  - Revisa conexion.
  - PokeAPI puede tener fallos temporales o rate limit.
  - La app ya tiene reintentos con backoff.

- **No aparecen sprites**:
  - Verifica internet.
  - Reintenta (algunas URLs pueden tardar en responder).

## Roadmap sugerido

- Cache persistente en disco para PokeAPI (modo offline).
- UI con tema avanzado (dark/light y badges de tipo).
- Exportar snapshots del equipo.
- Empaquetado como `.exe` (PyInstaller).

## Aviso

Proyecto fan-made sin afiliacion oficial con Nintendo, Game Freak o The Pokemon Company.

