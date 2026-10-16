// SPDX-License-Identifier: GPL-3.0-or-later
using System;
using System.IO;
using System.Text.Json;
using ProtoBuf;
using Save=EA.Sims4.Persistence;

namespace TS4SimRipper {
internal static class ApexWorkerTests {
    static byte[] Map(int bytes,byte compression,byte robe,byte[] data) {
        using var stream=new MemoryStream();using var writer=new BinaryWriter(stream);
        writer.Write(9u);writer.Write(4u);writer.Write(1u);writer.Write(4216u);writer.Write(1u);
        writer.Write((byte)0);writer.Write((byte)0);writer.Write((byte)bytes);writer.Write((byte)0);writer.Write((byte)2);
        writer.Write(0u);writer.Write(1u);writer.Write(0u);writer.Write(0u);writer.Write(robe);
        writer.Write(-1f);writer.Write(2f);if(robe==0){writer.Write(-2f);writer.Write(4f);}
        int extent=(compression==2?3:4)+data.Length;writer.Write(extent);writer.Write((ushort)extent);writer.Write(compression);
        if(compression!=2)writer.Write(robe);writer.Write(data);return stream.ToArray();
    }
    static MorphMap Read(byte[] raw){using var stream=new MemoryStream(raw);using var reader=new BinaryReader(stream);return new DMap(reader).ToMorphMap();}
    static void Close(float actual,float expected){if(Math.Abs(actual-expected)>.00001f)throw new Exception("Deformer value differs: "+actual+" / "+expected);}
    public static int Run() {
        try {
            var neutral=Read(Map(4,0,2,new byte[]{0,4,32,128,0,4,32,128}));
            var vector=neutral.GetAdjustedDelta(0,0,false,0);Close(vector.X,0);Close(vector.Y,0);Close(vector.Z,0);
            var normal=Read(Map(3,0,1,new byte[]{255,128,0,0,255,128}));
            vector=normal.GetAdjustedDelta(0,0,false,0);Close(vector.X,1);Close(vector.Y,0);Close(vector.Z,-1);
            vector=normal.GetAdjustedDelta(0,0,false,63);Close(vector.X,0);Close(vector.Z,0);
            var copy=Read(Map(3,0,2,new byte[]{255,128,0,0,255,128}));
            vector=copy.GetAdjustedDelta(0,0,false,63);Close(vector.X,1);Close(vector.Z,-1);
            // One run of two pixels; two lookup entries point to that run.
            var run=new byte[]{2,0,0,0,0,0,0,0,0,2,255,128,0};
            var compressed=Read(Map(3,1,2,run));
            vector=compressed.GetAdjustedDelta(1,0,false,0);Close(vector.X,1);Close(vector.Z,-1);
            vector=Read(Map(3,2,1,Array.Empty<byte>())).GetAdjustedDelta(0,0,false,0);Close(vector.X,0);
            var invalid=Map(3,1,2,run);invalid[invalid.Length-4]=0;
            try{Read(invalid);throw new Exception("Zero RLE run accepted.");}catch(InvalidDataException){}
            invalid=Map(4,0,2,new byte[8]);invalid[24]=255;
            try{Read(invalid);throw new Exception("Unknown packed format accepted.");}catch(InvalidDataException){}
            invalid=Map(3,0,2,new byte[6]);BitConverter.GetBytes(uint.MaxValue).CopyTo(invalid,37);
            try{Read(invalid);throw new Exception("Unbounded deformer dimensions accepted.");}catch(InvalidDataException){}
            var face=new Save.BlobSimFacialCustomizationData();
            face.face_modifiers.Add(new Save.BlobSimFacialCustomizationData.Modifier{key=1,amount=.2f});
            face.face_modifiers.Add(new Save.BlobSimFacialCustomizationData.Modifier{key=2,amount=.3f});
            face.aged_face_modifiers.Add(new Save.BlobSimFacialCustomizationData.Modifier{key=1,amount=.8f});
            var merged=Form1.ApexEffectiveFaceModifiers(face);if(merged.Count!=2)throw new Exception("Face modifiers lost.");
            Close(merged.Find(x=>x.key==1).amount,.8f);Close(merged.Find(x=>x.key==2).amount,.3f);Close(face.face_modifiers[0].amount,.2f);
            face.body_modifiers.Add(new Save.BlobSimFacialCustomizationData.Modifier{key=3,amount=.2f});
            face.aged_body_modifiers.Add(new Save.BlobSimFacialCustomizationData.Modifier{key=3,amount=.7f});
            Close(Form1.ApexEffectiveBodyModifiers(face).Find(x=>x.key==3).amount,.7f);Close(face.body_modifiers[0].amount,.2f);
            foreach(var outfit in new Save.OutfitData[]{null,new Save.OutfitData()}) {
                try{Form1.ApexRequirePreviewOutfit(outfit);throw new Exception("Missing outfit parts accepted.");}
                catch(InvalidDataException error){if(!error.Message.Contains("no equipped CAS parts"))throw;}
            }
            var traySim=new Save.SimData{sim_id=123,first_name="Tray",last_name="Fixture",physique="0.1,0.2",skin_tone=42,voice_pitch=-.14f,skin_tone_val_shift=.18f,
                attributes=new Save.PersistableSimInfoAttributes{occult_tracker=new Save.PersistableOccultTracker{current_occult_types=1}}};
            traySim.attributes.occult_tracker.occult_sim_infos.Add(new Save.PersistableOccultTracker.OccultSimData{occult_type=2,physique="Alien shape",skin_tone=77});
            using var trayBytes=new MemoryStream();Serializer.Serialize(trayBytes,traySim);
            using var trayRequest=JsonDocument.Parse(JsonSerializer.Serialize(new{sims=new[]{Convert.ToBase64String(trayBytes.ToArray())}}));
            using var trayResult=JsonDocument.Parse(JsonSerializer.Serialize(ApexTray.Inspect(trayRequest.RootElement)));
            var trayForms=trayResult.RootElement.GetProperty("sims")[0].GetProperty("forms");
            if(trayForms.GetArrayLength()!=2||trayForms[0].GetProperty("form").GetUInt32()!=2||
                trayForms[0].GetProperty("fields").GetProperty("skin_tone").GetProperty("value").GetUInt64()!=77||
                trayForms[1].GetProperty("fields").GetProperty("skin_tone").GetProperty("value").GetUInt64()!=42)
                throw new Exception("Tray stored/base appearance ownership differs.");
            var trayBase=trayForms[1].GetProperty("fields");
            if(trayBase.GetProperty("voice_pitch").GetProperty("value").GetDouble()!=(double)traySim.voice_pitch||
                trayBase.GetProperty("skin_tone_val_shift").GetProperty("value").GetDouble()!=(double)traySim.skin_tone_val_shift)
                throw new Exception("Tray binary32 values lost exact Python/native readback precision.");
            var thumbnailOutfit=new Save.OutfitData{outfit_id=789,category=5,parts=new EA.Sims4.IdList{ids=new ulong[]{10,20,30}},
                body_types_list=new Save.BodyTypesList{body_types=new uint[]{2,7,2}},part_shifts=new Save.ColorShiftList{color_shift=new ulong[]{11,22,33}},
                object_ids=new Save.ObjectIdsList{object_id=new ulong[]{44,55,66}},layer_ids=new Save.LayerIdsList{layer_id=new uint[]{1,2,3}}};
            Form1.ApexThumbnailPart(thumbnailOutfit,2,99,8);
            if(thumbnailOutfit.outfit_id!=789||thumbnailOutfit.category!=5||thumbnailOutfit.parts.ids.Length!=2||
                thumbnailOutfit.parts.ids[0]!=20||thumbnailOutfit.parts.ids[1]!=99||thumbnailOutfit.part_shifts.color_shift[0]!=22||
                thumbnailOutfit.object_ids.object_id[0]!=55||thumbnailOutfit.layer_ids.layer_id[0]!=2||thumbnailOutfit.layer_ids.layer_id[1]!=8)
                throw new Exception("Detached thumbnail replacement lost an unrelated layer or outfit identity.");
            thumbnailOutfit.object_ids.object_id=new ulong[]{1};
            try{Form1.ApexThumbnailPart(thumbnailOutfit,2,100,8);throw new Exception("Misaligned thumbnail arrays accepted.");}catch(InvalidDataException){}
            Console.WriteLine(JsonSerializer.Serialize(new{ok=true,modern_deformer_scenarios=8,aged_face_override=true,aged_body_override=true,empty_outfit_refused=true,native_face_data_unchanged=true,tray_native_float_precision=true,thumbnail_parallel_rows=true,game_contacted=false}));return 0;
        }catch(Exception error){Console.Error.WriteLine(error);return 1;}
    }
}
}
