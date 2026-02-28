"""
UI que muestra el equipo del save con sprites y datos (wrapper + PokeAPI).
Al hacer clic en un Pokémon se abre la info de Pokédex.
"""
import json
import os
import subprocess
import sys
import threading
import time
from io import BytesIO

RUTA_PROYECTO = r"C:\Users\danie\Documents\HUD-PokeCompanion\PokeLastCatch"
RUTA_SAVE = r"C:\Users\danie\AppData\Roaming\Azahar\sdmc\Nintendo 3DS\00000000000000000000000000000000\00000000000000000000000000000000\title\00040000\001b5100\data\00000001\main"

# Tamaño del sprite en la UI
SPRITE_SIZE = 96
SPRITE_POKEDEX = 128
POLL_SECONDS = 1.0
SAVE_DEBOUNCE_SECONDS = 0.6
LOG_EVO_API = True


def leer_wrapper(ruta_save: str = RUTA_SAVE):
    proc = subprocess.run(
        ["dotnet", "run", "--project", RUTA_PROYECTO, "--", ruta_save],
        capture_output=True,
        text=True,
        cwd=RUTA_PROYECTO,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "Error al ejecutar wrapper")
    return json.loads(proc.stdout)


def main():
    try:
        import requests
        from PIL import Image, ImageTk
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError as e:
        print("Dependencias necesarias: pip install requests Pillow")
        sys.exit(1)

    session = requests.Session()
    session.headers.update({"User-Agent": "HUD-PokeCompanion/1.0"})

    species_names_cache = {}
    pokemon_data_cache = {}
    species_data_cache = {}
    evolution_info_cache = {}

    def api_get_json(url, timeout=12, retries=3, log=False, log_tag="api"):
        last_error = None
        for attempt in range(retries):
            t0 = time.perf_counter()
            try:
                r = session.get(url, timeout=timeout)
                r.raise_for_status()
                if log and LOG_EVO_API:
                    ms = int((time.perf_counter() - t0) * 1000)
                    print(f"[{log_tag}] OK intento {attempt + 1}/{retries} [{r.status_code}] {ms}ms -> {url}", flush=True)
                return r.json()
            except requests.RequestException as ex:
                last_error = ex
                if log and LOG_EVO_API:
                    ms = int((time.perf_counter() - t0) * 1000)
                    status = "-"
                    if getattr(ex, "response", None) is not None:
                        status = str(ex.response.status_code)
                    print(f"[{log_tag}] ERROR intento {attempt + 1}/{retries} [HTTP {status}] {ms}ms -> {url} | {ex}", flush=True)
                # Backoff simple para absorber fallos temporales / rate limit.
                time.sleep(0.35 * (attempt + 1))
        if log and LOG_EVO_API:
            print(f"[{log_tag}] FALLO FINAL tras {retries} intentos -> {url}", flush=True)
        raise last_error if last_error else RuntimeError("Error consultando API")

    def cargar_sprite(url, size=SPRITE_SIZE):
        if not url:
            return None
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            img = Image.open(BytesIO(r.content)).convert("RGBA")
            img = img.resize((size, size), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    def obtener_datos_pokeapi(species_id):
        if species_id in pokemon_data_cache:
            pj = pokemon_data_cache[species_id]
            nombre = pj["name"].capitalize()
            sprite_url = (
                pj["sprites"].get("front_default")
                or pj["sprites"].get("front_female")
                or ""
            )
            return nombre, sprite_url
        try:
            r = requests.get(
                f"https://pokeapi.co/api/v2/pokemon/{species_id}",
                timeout=10,
            )
            r.raise_for_status()
            pj = r.json()
            pokemon_data_cache[species_id] = pj
            nombre = pj["name"].capitalize()
            sprite_url = (
                pj["sprites"].get("front_default")
                or pj["sprites"].get("front_female")
                or ""
            )
            return nombre, sprite_url
        except Exception:
            return f"Species {species_id}", ""

    def _extract_id_from_url(url):
        try:
            return int(url.rstrip("/").split("/")[-1])
        except Exception:
            return None

    def _get_species_json(species_id):
        if species_id in species_data_cache:
            return species_data_cache[species_id]
        data = api_get_json(
            f"https://pokeapi.co/api/v2/pokemon-species/{species_id}",
            timeout=12,
            retries=4,
            log=True,
            log_tag=f"evo-species-{species_id}",
        )
        species_data_cache[species_id] = data
        return data

    def _get_pokemon_json(pokemon_id):
        if pokemon_id in pokemon_data_cache:
            return pokemon_data_cache[pokemon_id]
        data = api_get_json(
            f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}",
            timeout=12,
            retries=4,
            log=True,
            log_tag=f"evo-pokemon-{pokemon_id}",
        )
        pokemon_data_cache[pokemon_id] = data
        return data

    def _format_evolution_condition(details):
        """Normaliza evolution_details de PokeAPI a un texto legible."""
        if not details:
            return "Condicion especial"

        # Helpers para nombres legibles
        def norm_name(node, fallback=""):
            if not node:
                return fallback
            return str(node.get("name", fallback)).replace("-", " ").title()

        min_level = details.get("min_level")
        item_name = norm_name(details.get("item"))
        held_item = norm_name(details.get("held_item"))
        trigger = norm_name(details.get("trigger"), "Especial")
        min_happiness = details.get("min_happiness")
        min_affection = details.get("min_affection")
        min_beauty = details.get("min_beauty")
        time_of_day = details.get("time_of_day", "")
        known_move = norm_name(details.get("known_move"))
        known_move_type = norm_name(details.get("known_move_type"))
        location = norm_name(details.get("location"))
        trade_species = norm_name(details.get("trade_species"))

        # Prioridad de condiciones frecuentes
        if min_level is not None:
            extra = []
            if time_of_day:
                extra.append(f"de {time_of_day}")
            if known_move:
                extra.append(f"con {known_move}")
            if location:
                extra.append(f"en {location}")
            return "Nivel " + str(min_level) + (f" ({', '.join(extra)})" if extra else "")

        if item_name:
            return f"Usar {item_name}"

        if trigger == "Trade":
            if held_item:
                return f"Intercambio con {held_item}"
            if trade_species:
                return f"Intercambio por {trade_species}"
            return "Intercambio"

        if min_happiness is not None:
            return f"Amistad {min_happiness}+"
        if min_affection is not None:
            return f"Afecto {min_affection}+"
        if min_beauty is not None:
            return f"Belleza {min_beauty}+"
        if known_move:
            return f"Conoce {known_move}"
        if known_move_type:
            return f"Conoce movimiento tipo {known_move_type}"
        if location:
            return f"Subir nivel en {location}"

        return trigger

    def obtener_siguiente_evolucion(species_id):
        """
        Devuelve:
        {
            "status": "ok" | "no_evolution" | "error",
            "next": [{"id", "name", "min_level", "condition", "sprite_url"}, ...]
        }
        """
        try:
            species_id = int(species_id)
        except Exception:
            return {"status": "error", "next": []}

        if species_id in evolution_info_cache:
            return evolution_info_cache[species_id]

        try:
            species_json = _get_species_json(species_id)
            chain_url = species_json.get("evolution_chain", {}).get("url", "")
            if not chain_url:
                result = {"status": "no_evolution", "next": []}
                evolution_info_cache[species_id] = result
                return result

            chain_json = api_get_json(
                chain_url,
                timeout=12,
                retries=4,
                log=True,
                log_tag=f"evo-chain-{species_id}",
            ).get("chain", {})

            # Buscar nodo actual en el árbol de evolución
            def find_node(node):
                node_id = _extract_id_from_url(node.get("species", {}).get("url", ""))
                if node_id == species_id:
                    return node
                for child in node.get("evolves_to", []):
                    found = find_node(child)
                    if found is not None:
                        return found
                return None

            current_node = find_node(chain_json)
            if not current_node:
                result = {"status": "error", "next": []}
                return result

            next_entries = []
            for evo in current_node.get("evolves_to", []):
                evo_species_id = _extract_id_from_url(evo.get("species", {}).get("url", ""))
                evo_name = evo.get("species", {}).get("name", "").replace("-", " ").title()
                details = (evo.get("evolution_details") or [{}])[0]
                min_level = details.get("min_level")
                condition = _format_evolution_condition(details)

                sprite_url = ""
                if evo_species_id is not None:
                    try:
                        evo_pok = _get_pokemon_json(evo_species_id)
                        sprite_url = (
                            evo_pok.get("sprites", {}).get("front_default")
                            or evo_pok.get("sprites", {}).get("front_female")
                            or ""
                        )
                    except Exception:
                        sprite_url = ""

                next_entries.append(
                    {
                        "id": evo_species_id,
                        "name": evo_name or (f"Species {evo_species_id}" if evo_species_id else "Desconocido"),
                        "min_level": min_level,
                        "condition": condition,
                        "sprite_url": sprite_url,
                    }
                )

            result = {
                "status": "ok" if next_entries else "no_evolution",
                "next": next_entries,
            }
            evolution_info_cache[species_id] = result
            return result
        except Exception as ex:
            # No cacheamos fallos de red/timeout para permitir reintentos.
            if LOG_EVO_API:
                print(f"[evo-{species_id}] ERROR resolviendo cadena evolutiva: {ex}", flush=True)
            return {"status": "error", "next": []}

    def obtener_nombres_especies(max_species):
        """Obtiene nombres de especies por ID usando pokemon-species."""
        if max_species in species_names_cache:
            return species_names_cache[max_species]

        mapping = {}
        try:
            r = requests.get(
                f"https://pokeapi.co/api/v2/pokemon-species?limit={max_species}",
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
            for item in data.get("results", []):
                name = item.get("name", "")
                url = item.get("url", "")
                if not url:
                    continue
                try:
                    species_id = int(url.rstrip("/").split("/")[-1])
                except Exception:
                    continue
                mapping[species_id] = name.replace("-", " ").title()
        except Exception:
            # Fallback silencioso: dejamos IDs sin nombre.
            pass

        species_names_cache[max_species] = mapping
        return mapping

    def obtener_info_pokedex(species_id):
        """Obtiene datos completos de pokemon, species y types para la ventana Pokédex."""
        try:
            r_pok = requests.get(
                f"https://pokeapi.co/api/v2/pokemon/{species_id}",
                timeout=10,
            )
            r_pok.raise_for_status()
            pok = r_pok.json()
            r_sp = requests.get(
                f"https://pokeapi.co/api/v2/pokemon-species/{species_id}",
                timeout=10,
            )
            r_sp.raise_for_status()
            sp = r_sp.json()

            types = [t["type"]["name"] for t in pok.get("types", [])]
            type_names = [t.capitalize() for t in types]

            # Debilidades, resistencias e inmunidades (agregando todos los tipos)
            damage_mult = {}
            for t in types:
                r_ty = requests.get(f"https://pokeapi.co/api/v2/type/{t}", timeout=10)
                r_ty.raise_for_status()
                ty = r_ty.json()
                dr = ty.get("damage_relations", {})
                for weak in dr.get("double_damage_from", []):
                    n = weak["name"]
                    damage_mult[n] = damage_mult.get(n, 1) * 2
                for res in dr.get("half_damage_from", []):
                    n = res["name"]
                    damage_mult[n] = damage_mult.get(n, 1) * 0.5
                for imm in dr.get("no_damage_from", []):
                    damage_mult[imm["name"]] = 0
            weaknesses = [name.capitalize() for name, mult in damage_mult.items() if mult > 1]
            resistances = [name.capitalize() for name, mult in damage_mult.items() if 0 < mult < 1]
            immunities = [name.capitalize() for name, mult in damage_mult.items() if mult == 0]

            # Stats base
            stat_names_es = {"hp": "PS", "attack": "Ataque", "defense": "Defensa",
                            "special-attack": "At. Esp.", "special-defense": "Def. Esp.", "speed": "Velocidad"}
            stats = []
            for s in pok.get("stats", []):
                name = s["stat"]["name"]
                stats.append((stat_names_es.get(name, name), s["base_stat"]))

            # Habilidades
            abilities = []
            for a in pok.get("abilities", []):
                name = a["ability"]["name"].replace("-", " ").title()
                if a.get("is_hidden"):
                    name += " (oculta)"
                abilities.append(name)

            # Movimientos que puede aprender (Gen 7: ultra-sun-ultra-moon o sun-moon)
            moves_level = []
            moves_tm = []
            moves_egg = []
            moves_tutor = []
            for m in pok.get("moves", []):
                move_name = m["move"]["name"].replace("-", " ").title()
                for vg in m.get("version_group_details", []):
                    if vg.get("version_group", {}).get("name") in ("ultra-sun-ultra-moon", "sun-moon"):
                        method = vg.get("move_learn_method", {}).get("name", "")
                        level = vg.get("level_learned_at", 0)
                        if method == "level-up":
                            moves_level.append((level, move_name))
                        elif method == "machine":
                            moves_tm.append(move_name)
                        elif method == "egg":
                            moves_egg.append(move_name)
                        elif method == "tutor":
                            moves_tutor.append(move_name)
                        break
            moves_level.sort(key=lambda x: x[0])
            moves_tm = list(dict.fromkeys(moves_tm))
            moves_egg = list(dict.fromkeys(moves_egg))
            moves_tutor = list(dict.fromkeys(moves_tutor))

            # Descripción y género en español
            flavor = ""
            for e in sp.get("flavor_text_entries", []):
                if e.get("language", {}).get("name") == "es":
                    flavor = e.get("flavor_text", "").replace("\n", " ")
                    break
            if not flavor and sp.get("flavor_text_entries"):
                flavor = sp["flavor_text_entries"][0].get("flavor_text", "").replace("\n", " ")
            genus = ""
            for g in sp.get("genera", []):
                if g.get("language", {}).get("name") == "es":
                    genus = g.get("genus", "")
                    break
            if not genus and sp.get("genera"):
                genus = sp["genera"][0].get("genus", "")

            return {
                "name": pok["name"].capitalize(),
                "sprite_url": pok["sprites"].get("front_default") or pok["sprites"].get("front_female") or "",
                "types": type_names,
                "height": pok.get("height", 0) / 10.0,
                "weight": pok.get("weight", 0) / 10.0,
                "flavor_text": flavor,
                "genus": genus,
                "stats": stats,
                "abilities": abilities,
                "weaknesses": weaknesses,
                "resistances": resistances,
                "immunities": immunities,
                "moves_level": moves_level,
                "moves_tm": moves_tm,
                "moves_egg": moves_egg,
                "moves_tutor": moves_tutor,
            }
        except Exception:
            return None

    def abrir_pokedex(species_id, nickname="", level=""):
        info = obtener_info_pokedex(species_id)
        if not info:
            messagebox.showerror("Error", "No se pudo cargar la información de la Pokédex.")
            return
        win = tk.Toplevel(root)
        win.title(f"Pokédex — {info['name']}")
        win.geometry("420x560")
        win.resizable(True, True)

        # Área con scroll
        canvas = tk.Canvas(win, highlightthickness=0)
        scrollbar = ttk.Scrollbar(win, orient=tk.VERTICAL, command=canvas.yview)
        f = ttk.Frame(canvas, padding=16)
        f.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=f, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _on_close():
            try:
                canvas.unbind_all("<MouseWheel>")
            except Exception:
                pass
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", _on_close)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Sprite y título
        photo = cargar_sprite(info["sprite_url"], size=SPRITE_POKEDEX)
        if photo:
            ttk.Label(f, image=photo).image = photo
            ttk.Label(f, image=photo).pack(pady=(0, 6))
        titulo = info["name"]
        if nickname and nickname.strip():
            titulo = f"{nickname} ({info['name']})"
        if level not in ("", "?"):
            titulo += f" — Nivel {level}"
        ttk.Label(f, text=titulo, font=("Segoe UI", 12, "bold")).pack()
        if info.get("genus"):
            ttk.Label(f, text=info["genus"], font=("Segoe UI", 10)).pack()
        if info.get("types"):
            ttk.Label(f, text="Tipo(s): " + ", ".join(info["types"]), font=("Segoe UI", 10)).pack()
        ttk.Label(f, text=f"Altura: {info['height']:.1f} m  |  Peso: {info['weight']:.1f} kg", font=("Segoe UI", 10)).pack(pady=(2, 8))
        if info.get("flavor_text"):
            ttk.Label(f, text=info["flavor_text"], font=("Segoe UI", 9), wraplength=360, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 10))

        def sep(title):
            ttk.Separator(f, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(8, 4))
            ttk.Label(f, text=title, font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)

        # Estadísticas base
        sep("Estadísticas base")
        stats_text = "  |  ".join(f"{n}: {v}" for n, v in info.get("stats", []))
        ttk.Label(f, text=stats_text, font=("Segoe UI", 9), wraplength=360).pack(anchor=tk.W)

        # Habilidades
        if info.get("abilities"):
            sep("Habilidades")
            ttk.Label(f, text=", ".join(info["abilities"]), font=("Segoe UI", 9), wraplength=360).pack(anchor=tk.W)

        # Debilidades / Resistencias / Inmunidades
        sep("Daño por tipo")
        parts = []
        if info.get("weaknesses"):
            parts.append("Debilidades: " + ", ".join(info["weaknesses"]))
        if info.get("resistances"):
            parts.append("Resistencias: " + ", ".join(info["resistances"]))
        if info.get("immunities"):
            parts.append("Inmunidades: " + ", ".join(info["immunities"]))
        if parts:
            ttk.Label(f, text="\n".join(parts), font=("Segoe UI", 9), wraplength=360).pack(anchor=tk.W)
        else:
            ttk.Label(f, text="—", font=("Segoe UI", 9)).pack(anchor=tk.W)

        # Movimientos por nivel
        if info.get("moves_level"):
            sep("Movimientos por nivel (Sube de nivel)")
            lines = [f"Nivel {lv}: {name}" for lv, name in info["moves_level"][:40]]
            if len(info["moves_level"]) > 40:
                lines.append(f"... y {len(info['moves_level']) - 40} más")
            ttk.Label(f, text="\n".join(lines), font=("Segoe UI", 9), wraplength=360, justify=tk.LEFT).pack(anchor=tk.W)

        # Movimientos por MT
        if info.get("moves_tm"):
            sep("Movimientos por MT")
            ttk.Label(f, text=", ".join(info["moves_tm"][:30]) + ("..." if len(info["moves_tm"]) > 30 else ""), font=("Segoe UI", 9), wraplength=360).pack(anchor=tk.W)

        # Movimientos por huevo
        if info.get("moves_egg"):
            sep("Movimientos por huevo")
            ttk.Label(f, text=", ".join(info["moves_egg"][:25]) + ("..." if len(info["moves_egg"]) > 25 else ""), font=("Segoe UI", 9), wraplength=360).pack(anchor=tk.W)

        # Movimientos por tutor
        if info.get("moves_tutor"):
            sep("Movimientos por tutor")
            ttk.Label(f, text=", ".join(info["moves_tutor"][:25]) + ("..." if len(info["moves_tutor"]) > 25 else ""), font=("Segoe UI", 9), wraplength=360).pack(anchor=tk.W)

    def abrir_pokedex_completa(dex_info):
        if not dex_info or not dex_info.get("Enabled"):
            messagebox.showinfo("Pokédex", "La Pokédex no está disponible en este save.")
            return

        max_species = int(dex_info.get("MaxSpecies") or 0)
        if max_species <= 0:
            messagebox.showinfo("Pokédex", "No hay especies disponibles para mostrar.")
            return

        seen_set = set(int(x) for x in (dex_info.get("SeenSpecies") or []))
        caught_set = set(int(x) for x in (dex_info.get("CaughtSpecies") or []))
        species_names = obtener_nombres_especies(max_species)

        win = tk.Toplevel(root)
        win.title("Pokédex completa")
        win.geometry("760x560")
        win.resizable(True, True)

        outer = ttk.Frame(win, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        controls = ttk.Frame(outer)
        controls.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(controls, text="Buscar:").pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(controls, textvariable=search_var, width=28)
        search_entry.pack(side=tk.LEFT, padx=(6, 14))

        ttk.Label(controls, text="Filtro:").pack(side=tk.LEFT)
        filter_var = tk.StringVar(value="Todos")
        filter_box = ttk.Combobox(
            controls,
            textvariable=filter_var,
            state="readonly",
            width=14,
            values=("Todos", "Vistos", "Capturados", "No vistos"),
        )
        filter_box.pack(side=tk.LEFT, padx=(6, 0))

        table_frame = ttk.Frame(outer)
        table_frame.pack(fill=tk.BOTH, expand=True)
        tree = ttk.Treeview(table_frame, columns=("id", "name", "status"), show="headings")
        tree.heading("id", text="ID")
        tree.heading("name", text="Especie")
        tree.heading("status", text="Estado")
        tree.column("id", width=80, anchor=tk.CENTER)
        tree.column("name", width=360, anchor=tk.W)
        tree.column("status", width=140, anchor=tk.CENTER)
        yscroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)

        info_lbl = ttk.Label(
            outer,
            text="Doble clic o Enter sobre una especie para abrir su ficha.",
            font=("Segoe UI", 9),
        )
        info_lbl.pack(anchor=tk.W, pady=(8, 0))

        def status_for_species(species_id):
            if species_id in caught_set:
                return "Capturado"
            if species_id in seen_set:
                return "Visto"
            return "No visto"

        def include_by_filter(status_text):
            mode = filter_var.get()
            if mode == "Vistos":
                return status_text in ("Visto", "Capturado")
            if mode == "Capturados":
                return status_text == "Capturado"
            if mode == "No vistos":
                return status_text == "No visto"
            return True

        def refresh_table(*_):
            query = search_var.get().strip().lower()
            tree.delete(*tree.get_children())
            for species_id in range(1, max_species + 1):
                status_text = status_for_species(species_id)
                if not include_by_filter(status_text):
                    continue

                species_name = species_names.get(species_id, f"Species {species_id}")
                if query:
                    if query not in species_name.lower() and query not in str(species_id):
                        continue
                tree.insert("", tk.END, values=(species_id, species_name, status_text))

        def open_selected(*_):
            selection = tree.selection()
            if not selection:
                return
            item = tree.item(selection[0])
            values = item.get("values") or []
            if not values:
                return
            species_id = int(values[0])
            species_name = str(values[1])
            abrir_pokedex(species_id, species_name, "")

        search_var.trace_add("write", refresh_table)
        filter_box.bind("<<ComboboxSelected>>", refresh_table)
        tree.bind("<Double-1>", open_selected)
        tree.bind("<Return>", open_selected)
        search_entry.focus_set()
        refresh_table()

    root = tk.Tk()
    root.title("HUD PokeCompanion — Equipo")
    root.resizable(True, True)
    root.configure(bg="#1a1a2e")
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("Card.TLabelframe", padding=10)
    style.configure("CardTitle.TLabel", font=("Segoe UI", 11, "bold"))
    style.configure("Subtle.TLabel", font=("Segoe UI", 9))

    # Marco principal con padding
    main = ttk.Frame(root, padding=16)
    main.pack(fill=tk.BOTH, expand=True)

    # Título
    titulo = ttk.Label(
        main,
        text="Tu equipo (Ultra Luna)",
        font=("Segoe UI", 14, "bold"),
    )
    titulo.pack(pady=(0, 12))
    status_var = tk.StringVar(value="Cargando save...")
    ttk.Label(main, textvariable=status_var, font=("Segoe UI", 9)).pack(pady=(0, 10))
    content = ttk.Frame(main)
    content.pack(fill=tk.BOTH, expand=True)

    def render_data(datos):
        for child in content.winfo_children():
            child.destroy()

        trainer = datos.get("Trainer") or {}
        dex = datos.get("Pokedex") or {}
        party = datos.get("Party") or []
        last = datos.get("Last") or {}

        # Resumen superior: entrenador + progreso de Pokédex
        summary = ttk.Frame(content)
        summary.pack(fill=tk.X, pady=(0, 10))

        trainer_frame = ttk.LabelFrame(summary, text="Entrenador", padding=10)
        trainer_frame.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        dex_frame = ttk.LabelFrame(summary, text="Pokédex", padding=10)
        dex_frame.grid(row=0, column=1, padx=(8, 0), sticky="nsew")
        summary.columnconfigure(0, weight=1)
        summary.columnconfigure(1, weight=1)

        trainer_name = trainer.get("Name") or "—"
        trainer_tid = trainer.get("TID")
        trainer_sid = trainer.get("SID")
        trainer_money = trainer.get("Money")
        trainer_play = trainer.get("PlayTime") or "—"
        game_version = trainer.get("GameVersion") or "—"

        money_txt = f"${trainer_money:,}" if isinstance(trainer_money, int) else "—"
        tid_txt = f"{trainer_tid:05d}" if isinstance(trainer_tid, int) and trainer_tid >= 0 else "—"
        sid_txt = f"{trainer_sid:04d}" if isinstance(trainer_sid, int) and trainer_sid >= 0 else "—"

        ttk.Label(trainer_frame, text=f"Nombre: {trainer_name}", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(trainer_frame, text=f"TID/SID: {tid_txt} / {sid_txt}", font=("Segoe UI", 9)).pack(anchor=tk.W)
        ttk.Label(trainer_frame, text=f"Dinero: {money_txt}", font=("Segoe UI", 9)).pack(anchor=tk.W)
        ttk.Label(trainer_frame, text=f"Tiempo jugado: {trainer_play}", font=("Segoe UI", 9)).pack(anchor=tk.W)
        ttk.Label(trainer_frame, text=f"Versión: {game_version}", font=("Segoe UI", 9)).pack(anchor=tk.W)

        dex_enabled = bool(dex.get("Enabled"))
        if dex_enabled:
            seen = dex.get("Seen", 0)
            caught = dex.get("Caught", 0)
            max_species = dex.get("MaxSpecies", 0)
            seen_pct = dex.get("SeenPercent", 0)
            caught_pct = dex.get("CaughtPercent", 0)
            ttk.Label(dex_frame, text=f"Vistos: {seen} / {max_species}", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
            ttk.Label(dex_frame, text=f"Capturados: {caught} / {max_species}", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
            ttk.Label(dex_frame, text=f"Vistos (%): {seen_pct}%", font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(4, 0))
            ttk.Label(dex_frame, text=f"Capturados (%): {caught_pct}%", font=("Segoe UI", 9)).pack(anchor=tk.W)
            ttk.Button(
                dex_frame,
                text="Abrir Pokédex completa",
                command=lambda d=dex: abrir_pokedex_completa(d),
            ).pack(anchor=tk.W, pady=(8, 0))
        else:
            ttk.Label(dex_frame, text="Pokédex no disponible en este save.", font=("Segoe UI", 9)).pack(anchor=tk.W)

        if not party:
            ttk.Label(content, text="No hay Pokémon en el equipo.").pack(pady=20)
            return

        # Contenedor de fichas (grid)
        frame_party = ttk.Frame(content)
        frame_party.pack(fill=tk.BOTH, expand=True)
        cards_per_row = 3

        for i, mon in enumerate(party):
            species_id = mon["SpeciesId"]
            nickname = mon.get("Nickname") or ""
            level = mon.get("Level", "?")
            friendship = mon.get("Friendship", -1)

            nombre_api, sprite_url = obtener_datos_pokeapi(species_id)
            photo = cargar_sprite(sprite_url)

            row = i // cards_per_row
            col = i % cards_per_row
            frame_party.columnconfigure(col, weight=1)

            # Ficha por Pokémon (clic para abrir Pokédex)
            card = ttk.LabelFrame(frame_party, text="", style="Card.TLabelframe")
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            # Capturar valores por iteración para que cada tarjeta abra su propio Pokémon.
            def on_click(e, _sid=species_id, _nick=nickname, _lvl=level):
                abrir_pokedex(_sid, _nick, str(_lvl))

            if photo:
                lbl_sprite = ttk.Label(card, image=photo, cursor="hand2")
                lbl_sprite.image = photo  # mantener referencia
                lbl_sprite.pack(pady=(0, 6))
                lbl_sprite.bind("<Button-1>", on_click)

            nombre_mostrar = nickname if nickname.strip() else nombre_api
            l1 = ttk.Label(card, text=nombre_mostrar, style="CardTitle.TLabel", cursor="hand2")
            l1.pack()
            l1.bind("<Button-1>", on_click)
            l2 = ttk.Label(card, text=nombre_api if nickname.strip() else "", style="Subtle.TLabel", cursor="hand2")
            l2.pack()
            l2.bind("<Button-1>", on_click)
            l3 = ttk.Label(card, text=f"Nivel {level}", font=("Segoe UI", 10), cursor="hand2")
            l3.pack()
            l3.bind("<Button-1>", on_click)
            if isinstance(friendship, int) and friendship >= 0:
                l4 = ttk.Label(card, text=f"Amistad: {friendship}/255", style="Subtle.TLabel", cursor="hand2")
                l4.pack()
                l4.bind("<Button-1>", on_click)
            card.bind("<Button-1>", on_click)

            # Información de evolución: siguiente(s) evolución(es), condición y sprite.
            evo_result = obtener_siguiente_evolucion(species_id)
            next_evos = evo_result.get("next", [])
            evo_status = evo_result.get("status", "error")
            # Resumen visible y rápido (siempre encima del bloque visual de evolución).
            if next_evos:
                first_evo = next_evos[0]
                cond = first_evo.get("condition", "") or "condición especial"
                evo_summary = f"Evoluciona a {first_evo.get('name', '—')} ({cond})"
                ttk.Label(card, text=evo_summary, font=("Segoe UI", 9, "bold")).pack(pady=(6, 0))
            elif evo_status == "error":
                ttk.Label(card, text="Evolución: no disponible (error de red/API)", style="Subtle.TLabel").pack(pady=(6, 0))
            else:
                ttk.Label(card, text="Sin evolución posterior", style="Subtle.TLabel").pack(pady=(6, 0))

            sep = ttk.Separator(card, orient=tk.HORIZONTAL)
            sep.pack(fill=tk.X, pady=(8, 6))
            if next_evos:
                ttk.Label(card, text="Próxima evolución", style="Subtle.TLabel").pack()
                evo_wrap = ttk.Frame(card)
                evo_wrap.pack(pady=(2, 0))
                for evo in next_evos[:2]:
                    evo_col = ttk.Frame(evo_wrap)
                    evo_col.pack(side=tk.LEFT, padx=6)
                    evo_photo = cargar_sprite(evo.get("sprite_url", ""), size=52)
                    if evo_photo:
                        evo_lbl = ttk.Label(evo_col, image=evo_photo, cursor="hand2")
                        evo_lbl.image = evo_photo
                        evo_lbl.pack()
                        if evo.get("id"):
                            evo_lbl.bind("<Button-1>", lambda e, sid=evo["id"], n=evo["name"]: abrir_pokedex(sid, n, ""))
                    evo_name_lbl = ttk.Label(evo_col, text=evo.get("name", "—"), style="Subtle.TLabel")
                    evo_name_lbl.pack()
                    cond = evo.get("condition", "") or "Método desconocido"
                    evo_cond_lbl = ttk.Label(evo_col, text=cond, style="Subtle.TLabel")
                    evo_cond_lbl.pack()
            elif evo_status == "error":
                ttk.Label(card, text="No se pudo consultar la cadena evolutiva ahora.", style="Subtle.TLabel").pack()

            ttk.Button(card, text="Ver ficha", command=lambda sid=species_id, n=nombre_mostrar, lv=level: abrir_pokedex(sid, n, str(lv))).pack(pady=(8, 0))

        # Último capturado (clic para abrir Pokédex)
        if last:
            last_frame = ttk.LabelFrame(content, text="Último capturado", padding=10)
            last_frame.pack(fill=tk.X, pady=(16, 0))
            last_id = last.get("SpeciesId")
            last_nick = last.get("Nickname") or ""
            last_friendship = last.get("Friendship", -1)
            last_nombre, last_sprite_url = obtener_datos_pokeapi(last_id)
            last_photo = cargar_sprite(last_sprite_url, size=64)
            inner = ttk.Frame(last_frame)
            inner.pack()

            def abrir_last():
                abrir_pokedex(last_id, last_nick, str(last.get("Level", "?")))

            if last_photo:
                lbl = ttk.Label(inner, image=last_photo, cursor="hand2")
                lbl.image = last_photo
                lbl.pack(side=tk.LEFT, padx=(0, 10))
                lbl.bind("<Button-1>", lambda e: abrir_last())
            last_txt = ttk.Label(
                inner,
                text=f"{last_nick or last_nombre} (Nivel {last.get('Level', '?')}) — Clic para Pokédex",
                font=("Segoe UI", 10),
                cursor="hand2",
            )
            last_txt.pack(side=tk.LEFT)
            last_txt.bind("<Button-1>", lambda e: abrir_last())
            last_frame.bind("<Button-1>", lambda e: abrir_last())
            if isinstance(last_friendship, int) and last_friendship >= 0:
                ttk.Label(
                    last_frame,
                    text=f"Amistad actual: {last_friendship}/255",
                    style="Subtle.TLabel",
                ).pack(anchor=tk.W, pady=(6, 0))

    def load_and_render(show_popup_on_error=False):
        try:
            datos = leer_wrapper(RUTA_SAVE)
            render_data(datos)
            status_var.set(f"Actualizado: {time.strftime('%H:%M:%S')}")
        except Exception as ex:
            status_var.set("Error al leer save. Reintentando...")
            if show_popup_on_error:
                messagebox.showerror("Error", f"No se pudo leer el save:\n{ex}")

    stop_event = threading.Event()

    def watch_save_loop():
        last_signature = None
        while not stop_event.is_set():
            try:
                st = os.stat(RUTA_SAVE)
                signature = (st.st_mtime_ns, st.st_size)
                if signature != last_signature:
                    last_signature = signature
                    time.sleep(SAVE_DEBOUNCE_SECONDS)
                    root.after(0, load_and_render)
            except FileNotFoundError:
                root.after(0, lambda: status_var.set("Archivo save no encontrado."))
            except Exception:
                root.after(0, lambda: status_var.set("Error monitoreando save."))
            time.sleep(POLL_SECONDS)

    load_and_render(show_popup_on_error=True)
    watcher = threading.Thread(target=watch_save_loop, daemon=True)
    watcher.start()

    def on_close():
        stop_event.set()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
