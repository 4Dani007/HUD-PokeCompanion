"""
Usa el wrapper PokeLastCatch para leer el save y muestra el equipo con datos de PokeAPI.
"""
import json
import subprocess
import sys

RUTA_PROYECTO = r"C:\Users\danie\Documents\HUD-PokeCompanion\PokeLastCatch"
RUTA_SAVE = r"C:\Users\danie\AppData\Roaming\Azahar\sdmc\Nintendo 3DS\00000000000000000000000000000000\00000000000000000000000000000000\title\00040000\001b5100\data\00000001\main"


def leer_wrapper(ruta_save: str = RUTA_SAVE):
    proc = subprocess.run(
        ["dotnet", "run", "--project", RUTA_PROYECTO, "--", ruta_save],
        capture_output=True,
        text=True,
        cwd=RUTA_PROYECTO,
    )
    if proc.returncode != 0:
        print("Error al ejecutar wrapper:", proc.stderr or proc.stdout, file=sys.stderr)
        sys.exit(1)
    return json.loads(proc.stdout)


def mostrar_equipo_con_pokeapi():
    try:
        import requests
    except ImportError:
        print("Instala requests: pip install requests")
        sys.exit(1)

    datos = leer_wrapper()

    if not datos.get("Party"):
        print("No hay Pokémon en el equipo.")
        return

    print("Equipo actual (datos del save + PokeAPI):\n")
    for mon in datos["Party"]:
        species_id = mon["SpeciesId"]
        nickname = mon["Nickname"]
        level = mon.get("Level", "?")

        try:
            r = requests.get(f"https://pokeapi.co/api/v2/pokemon/{species_id}", timeout=10)
            r.raise_for_status()
            pj = r.json()
            nombre_api = pj["name"]
            sprite = pj["sprites"].get("front_default") or pj["sprites"].get("front_female") or ""
        except Exception as e:
            nombre_api = f"Species {species_id}"
            sprite = ""
            print(f"  (PokeAPI error: {e})")

        print(f"  {nickname} ({nombre_api}) — Nivel {level} — SpeciesId: {species_id}")
        if sprite:
            print(f"    Sprite: {sprite}")
        print()

    last = datos.get("Last")
    if last:
        print(f"Último capturado: {last.get('Nickname')} (SpeciesId {last.get('SpeciesId')})")


if __name__ == "__main__":
    mostrar_equipo_con_pokeapi()
