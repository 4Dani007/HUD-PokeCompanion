using System;
using System.Text.Json;
using System.Collections.Generic;
using PKHeX.Core;

namespace PokeLastCatch
{
    internal static class Program
    {
        private static int Main(string[] args)
        {
            if (args.Length < 1)
            {
                Console.Error.WriteLine("Uso: PokeLastCatch <ruta_save>");
                return 1;
            }

            var savePath = args[0];

            try
            {
                // Carga el archivo de guardado en memoria.
                var data = System.IO.File.ReadAllBytes(savePath);

                // Intenta detectar automáticamente el tipo de guardado (Ultra Sol/Ultra Luna, etc.).
                // Usamos reflexión para adaptarnos a pequeñas diferencias de versión en PKHeX.Core.
                SaveFile? sav = null;
                var methods = typeof(SaveUtil).GetMethods();
                foreach (var m in methods)
                {
                    if (m.Name != "GetVariantSAV")
                        continue;

                    var ps = m.GetParameters();
                    if (ps.Length != 1)
                        continue;

                    object arg;
                    var paramType = ps[0].ParameterType;
                    if (paramType == typeof(byte[]))
                        arg = data;
                    else if (paramType == typeof(System.Memory<byte>))
                        arg = new System.Memory<byte>(data);
                    else
                        continue;

                    var result = m.Invoke(null, new[] { arg });
                    sav = result as SaveFile;
                    if (sav != null)
                        break;
                }

                if (sav == null)
                {
                    Console.Error.WriteLine("No se pudo reconocer el archivo de guardado.");
                    return 1;
                }

                PKM ultimoPkm = null;
                DateTime? ultimaFecha = null;
                var party = new List<object>();

                // Equipo actual
                for (int i = 0; i < sav.PartyCount; i++)
                {
                    var pkm = sav.GetPartySlotAtIndex(i);
                    if (pkm != null && pkm.Species != 0)
                    {
                        var friendship = GetIntProperty(
                            pkm,
                            "CurrentFriendship",
                            GetIntProperty(
                                pkm,
                                "OT_Friendship",
                                GetIntProperty(pkm, "HT_Friendship", -1)
                            )
                        );
                        party.Add(new
                        {
                            SpeciesId = (int)pkm.Species,
                            Species = pkm.Species.ToString(),
                            Nickname = pkm.Nickname,
                            MetDate = pkm.MetDate,
                            Level = pkm.CurrentLevel,
                            OT = pkm.OT_Name,
                            EncounterType = (int)pkm.EncounterType,
                            MetLocation = (int)pkm.Met_Location,
                            EggLocation = (int)pkm.Egg_Location,
                            Ball = (int)pkm.Ball,
                            IsEgg = pkm.IsEgg,
                            Friendship = friendship
                        });
                    }
                    ProcesarPokemon(pkm, ref ultimoPkm, ref ultimaFecha);
                }

                // Cajas
                for (int box = 0; box < sav.BoxCount; box++)
                {
                    for (int slot = 0; slot < sav.BoxSlotCount; slot++)
                    {
                        var pkm = sav.GetBoxSlotAtIndex(box, slot);
                        ProcesarPokemon(pkm, ref ultimoPkm, ref ultimaFecha);
                    }
                }

                if (ultimoPkm == null || ultimaFecha == null)
                {
                    Console.WriteLine("{}");
                    return 0;
                }

                var hasDex = sav.HasPokeDex;
                var maxSpecies = (int)sav.MaxSpeciesID;
                var seen = hasDex ? sav.SeenCount : 0;
                var caught = hasDex ? sav.CaughtCount : 0;
                var seenPercent = maxSpecies > 0 ? Math.Round((seen * 100.0) / maxSpecies, 2) : 0.0;
                var caughtPercent = maxSpecies > 0 ? Math.Round((caught * 100.0) / maxSpecies, 2) : 0.0;
                var tid = GetIntProperty(sav, "TID16", GetIntProperty(sav, "TID", -1));
                var sid = GetIntProperty(sav, "SID16", GetIntProperty(sav, "SID", -1));
                var seenSpecies = new List<int>();
                var caughtSpecies = new List<int>();
                if (hasDex)
                {
                    for (ushort species = 1; species <= sav.MaxSpeciesID; species++)
                    {
                        if (sav.GetSeen(species))
                            seenSpecies.Add(species);
                        if (sav.GetCaught(species))
                            caughtSpecies.Add(species);
                    }
                }

                var resultado = new
                {
                    Trainer = new
                    {
                        Name = sav.OT,
                        TID = tid,
                        SID = sid,
                        Money = sav.Money,
                        PlayTime = sav.PlayTimeString,
                        GameVersion = sav.Version.ToString(),
                        Generation = (int)sav.Generation
                    },
                    Pokedex = new
                    {
                        Enabled = hasDex,
                        Seen = seen,
                        Caught = caught,
                        MaxSpecies = maxSpecies,
                        SeenPercent = seenPercent,
                        CaughtPercent = caughtPercent,
                        SeenSpecies = seenSpecies,
                        CaughtSpecies = caughtSpecies
                    },
                    Last = new
                    {
                        SpeciesId = (int)ultimoPkm.Species,
                        Species = ultimoPkm.Species.ToString(),
                        Nickname = ultimoPkm.Nickname,
                        MetDate = ultimaFecha.Value.ToString("yyyy-MM-dd"),
                        Level = ultimoPkm.CurrentLevel,
                        OT = ultimoPkm.OT_Name,
                        Friendship = GetIntProperty(
                            ultimoPkm,
                            "CurrentFriendship",
                            GetIntProperty(
                                ultimoPkm,
                                "OT_Friendship",
                                GetIntProperty(ultimoPkm, "HT_Friendship", -1)
                            )
                        )
                    },
                    Party = party
                };

                var json = JsonSerializer.Serialize(resultado);
                Console.WriteLine(json);
                return 0;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("Error: " + ex.Message);
                return 1;
            }
        }

        private static void ProcesarPokemon(PKM pkm, ref PKM ultimoPkm, ref DateTime? ultimaFecha)
        {
            if (pkm == null || pkm.Species == 0)
                return;

            // En PKHeX.Core 20.11.28, MetDate está almacenada como una estructura DateTime.
            var fecha = pkm.MetDate;

            if (!ultimaFecha.HasValue || fecha > ultimaFecha.Value)
            {
                ultimaFecha = fecha;
                ultimoPkm = pkm;
            }
        }

        private static int GetIntProperty(object obj, string propertyName, int fallback)
        {
            var prop = obj.GetType().GetProperty(propertyName);
            if (prop == null)
                return fallback;

            var value = prop.GetValue(obj);
            if (value == null)
                return fallback;

            try
            {
                return Convert.ToInt32(value);
            }
            catch
            {
                return fallback;
            }
        }
    }
}
