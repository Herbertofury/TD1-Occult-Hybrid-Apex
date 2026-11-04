// SPDX-License-Identifier: GPL-3.0-or-later
// Exact Tray Sim projection through the worker's pinned EA protobuf schemas.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text.Json;
using ProtoBuf;
using Save=EA.Sims4.Persistence;
namespace TS4SimRipper {
internal static class ApexTray {
    // Python reads the exact binary32 value as a double. Serializing a boxed
    // float uses its shorter binary32 round-trip decimal, which is a different
    // Python double and fails exact native readback after a paste.
    static object Value(object value)=>new{kind="value",value=value is float number?(object)(double)number:value};
    static object Bytes(byte[] raw,string kind="bytes")=>new{kind,value=Convert.ToBase64String(raw??Array.Empty<byte>())};
    static byte[] Wire<T>(T value){if(value==null)return Array.Empty<byte>();using var s=new MemoryStream();Serializer.Serialize(s,value);return s.ToArray();}
    static Dictionary<string,object> Core(Save.SimData sim,Save.PersistableOccultTracker.OccultSimData occult=null){
        var result=new Dictionary<string,object>{
            ["physique"]=Value(occult?.physique??sim.physique),
            ["facial_attributes"]=Bytes(occult?.facial_attributes??sim.facial_attr),
            ["skin_tone"]=Value(occult!=null?occult.skin_tone:sim.skin_tone),
            ["skin_tone_val_shift"]=Value(occult!=null?occult.skin_tone_val_shift:sim.skin_tone_val_shift),
            ["genetic_data"]=Bytes(Wire(occult!=null?occult.genetic_data:sim.genetic_data)),
            ["pelt_layers"]=Bytes(Wire(sim.pelt_layers)),["custom_texture"]=Value(sim.custom_texture),
            ["voice_pitch"]=Value(occult!=null?occult.voice_pitch:sim.voice_pitch),
            ["voice_actor"]=Value(occult!=null?occult.voice_actor:sim.voice_actor),
            ["voice_effect"]=Value(occult!=null?occult.voice_effect:sim.voice_effect),
            ["__outfits__"]=Bytes(Wire(occult!=null?occult.outfits:sim.outfits),"protobuf")};
        var tattoos=occult!=null?occult.parts_custom_tattoos:sim.parts_custom_tattoos;
        result["parts_custom_tattoos"]=new{kind="mapping",value=tattoos.Select(t=>new object[]{Value(t.body_type),Value(t.texture_id)}).ToArray()};
        return result;
    }
    public static object Inspect(JsonElement request){
        var input=request.GetProperty("sims");if(input.GetArrayLength()>128)throw new InvalidDataException("Tray Sim count exceeds bound.");
        var result=new List<object>();var ids=new HashSet<ulong>();long bytes=0;
        foreach(var encoded in input.EnumerateArray()){
            var raw=Convert.FromBase64String(encoded.GetString());bytes+=raw.Length;
            if(raw.Length==0||raw.Length>7*1024*1024||bytes>8*1024*1024)throw new InvalidDataException("Tray Sim payload exceeds bound.");
            using var stream=new MemoryStream(raw);var sim=Serializer.Deserialize<Save.SimData>(stream);
            if(sim.sim_id==0||!ids.Add(sim.sim_id))throw new InvalidDataException("Tray Sim identity is missing or duplicated.");
            var forms=new List<object>();var kinds=new HashSet<uint>();
            var tracker=sim.attributes?.occult_tracker;uint current=tracker?.current_occult_types??1;if(current==0)current=1;
            if(tracker!=null)foreach(var occult in tracker.occult_sim_infos){
                uint form=occult.occult_type;if(!new uint[]{1,2,4,8,16,32,64}.Contains(form)||!kinds.Add(form))throw new InvalidDataException("Tray contains an unsupported or duplicate appearance owner.");
                forms.Add(new{form,fields=Core(sim,occult),source="stored",shared_fields=new[]{"pelt_layers","custom_texture"}});
            }
            if(!kinds.Contains(current))forms.Add(new{form=current,fields=Core(sim),source="base",shared_fields=Array.Empty<string>()});
            result.Add(new{sim_id=sim.sim_id.ToString(),name=(sim.first_name+" "+sim.last_name).Trim(),age=sim.age,gender=sim.gender,
                native_sim=Convert.ToBase64String(raw),native_sha256=Convert.ToHexString(SHA256.HashData(raw)).ToLowerInvariant(),forms});
        }
        return new{ok=true,sims=result,disk_assets_written=false,game_contacted=false};
    }
}
}
