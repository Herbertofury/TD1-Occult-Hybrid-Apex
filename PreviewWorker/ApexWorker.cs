// SPDX-License-Identifier: GPL-3.0-or-later
// SimRipper adapter. Upstream copyright C. Marinetti and contributors.
// Corresponding source: tools/build_preview_worker.py's pinned source archive
// plus this adapter and its deterministic transformations. Never shows a UI.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Windows.Forms;
using ProtoBuf;
using Save = EA.Sims4.Persistence;

namespace TS4SimRipper {
internal static class ApexDialog {
    public static DialogResult Fail(params object[] args) => throw new InvalidOperationException(String.Join(" ", args.Select(x => x?.ToString())));
}
internal static class ApexWorker {
    [STAThread] static int Main(string[] args) {
        if(args.Length==1&&args[0]=="--self-test")return ApexWorkerTests.Run();
        if (args.Length != 2 || !Directory.Exists(args[0]) || !Directory.Exists(args[1])) return 2;
        try {
            Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);
            Application.SetHighDpiMode(HighDpiMode.DpiUnaware);
            Properties.Settings.Default.TS4Path = Path.GetFullPath(args[0]);
            Properties.Settings.Default.TS4ModsPath = Path.GetFullPath(args[1]);
            Properties.Settings.Default.TS4ContentPath = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(args[1])), "content");
            Properties.Settings.Default.TS4SavesPath = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(args[1])), "saves");
            using var engine = new Form1();
            Console.WriteLine("{\"ok\":true,\"ready\":true,\"window_shown\":false}");
            string line;
            while ((line = Console.ReadLine()) != null) {
                string response;
                try {
                    if (line.Length > 16 * 1024 * 1024) throw new InvalidDataException("Preview request too large.");
                    using var json = JsonDocument.Parse(line);
                    response=JsonSerializer.Serialize(json.RootElement.TryGetProperty("operation",out var operation)
                        ? operation.GetString()=="tray-inspect" ? ApexTray.Inspect(json.RootElement)
                        : operation.GetString()=="thumbnail-outfit" ? engine.ApexThumbnailOutfit(json.RootElement)
                        : throw new InvalidDataException("Unknown worker operation.") : engine.ApexAssemble(json.RootElement));
                } catch (Exception e) { response=JsonSerializer.Serialize(new {ok=false,error=e.ToString()}); }
                finally {
                    engine.ApexReleaseImages();
                    engine.ApexReleaseAssembly();
                    // Upstream's morph maps and local GDI composites can hold
                    // gigabytes of temporary native/managed buffers. Release
                    // them after each response, rather than waiting for the
                    // machine-wide GC threshold across thousands of Sims.
                    GC.Collect(2,GCCollectionMode.Forced,true,true);
                    GC.WaitForPendingFinalizers();
                    GC.Collect(2,GCCollectionMode.Forced,true,true);
                }
                // Ready means temporary assembly buffers have been released.
                Console.WriteLine(response);
            }
            return 0;
        } catch (Exception e) { Console.WriteLine(JsonSerializer.Serialize(new {ok=false,error=e.ToString()})); return 1; }
    }
}
public partial class Form1 {
    // Aged modifiers override matching base keys, preserving all other face
    // modifiers. Matches the upstream fix discussed in SimRipper PR #105.
    internal static List<Save.BlobSimFacialCustomizationData.Modifier> ApexEffectiveFaceModifiers(Save.BlobSimFacialCustomizationData data) {
        return ApexEffectiveModifiers(data.face_modifiers,data.aged_face_modifiers);
    }
    internal static List<Save.BlobSimFacialCustomizationData.Modifier> ApexEffectiveBodyModifiers(Save.BlobSimFacialCustomizationData data) {
        return ApexEffectiveModifiers(data.body_modifiers,data.aged_body_modifiers);
    }
    static List<Save.BlobSimFacialCustomizationData.Modifier> ApexEffectiveModifiers(List<Save.BlobSimFacialCustomizationData.Modifier> basic,List<Save.BlobSimFacialCustomizationData.Modifier> aged) {
        var values=new Dictionary<ulong,float>();
        if(basic!=null)foreach(var item in basic)values[item.key]=item.amount;
        if(aged!=null)foreach(var item in aged)values[item.key]=item.amount;
        return values.Select(item=>new Save.BlobSimFacialCustomizationData.Modifier{key=item.Key,amount=item.Value}).ToList();
    }
    public void ApexReleaseAssembly() {
        CurrentModel=null;BaseModel=null;GlassModel=null;WingsModel=null;
        morphBGEO=null;morphShape=null;morphNormals=null;morphBOND=null;
        currentOutfits=null;
    }
    static byte[] Wire(JsonElement fields, string name) => Convert.FromBase64String(fields.GetProperty(name).GetProperty("value").GetString());
    static T Parse<T>(byte[] raw) { using var s = new MemoryStream(raw); return Serializer.Deserialize<T>(s); }
    static string Hash(byte[] raw) => Convert.ToHexString(SHA256.HashData(raw)).ToLowerInvariant();
    public void ApexReleaseImages() {
        var released=new HashSet<Image>();
        foreach(var field in GetType().GetFields(System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic))
            if(typeof(Image).IsAssignableFrom(field.FieldType)&&field.GetValue(this) is Image image){
                if(released.Add(image))image.Dispose();field.SetValue(this,null);
            }
    }
    public static void ApexRequirePreviewOutfit(Save.OutfitData outfit) {
        if (outfit?.parts?.ids == null || outfit.parts.ids.Length == 0)
            throw new InvalidDataException("This stored outfit has no equipped CAS parts. Choose a populated outfit or equip items on this form before previewing; another form's clothes will not be substituted.");
        if (outfit.parts.ids.Length > 4096)
            throw new InvalidDataException("Selected preview outfit exceeds its part bound.");
    }
    internal static void ApexThumbnailPart(Save.OutfitData outfit,uint body,ulong part,uint layer) {
        var ids=outfit.parts?.ids;var bodies=outfit.body_types_list?.body_types;
        if(ids==null||bodies==null||ids.Length!=bodies.Length||ids.Length>4096)throw new InvalidDataException("Ambiguous thumbnail outfit rows.");
        var shifts=outfit.part_shifts?.color_shift??Array.Empty<ulong>();
        var objects=outfit.object_ids?.object_id??Array.Empty<ulong>();var layers=outfit.layer_ids?.layer_id??Array.Empty<uint>();
        if(new[]{shifts.Length,objects.Length,layers.Length}.Any(n=>n!=0&&n!=ids.Length))throw new InvalidDataException("Thumbnail outfit arrays differ.");
        var kept=Enumerable.Range(0,ids.Length).Where(i=>bodies[i]!=body).ToList();
        outfit.parts.ids=kept.Select(i=>ids[i]).Append(part).ToArray();
        outfit.body_types_list.body_types=kept.Select(i=>bodies[i]).Append(body).ToArray();
        outfit.part_shifts=new Save.ColorShiftList{color_shift=kept.Select(i=>shifts.Length==0?4611686018427387904ul:shifts[i]).Append(4611686018427387904ul).ToArray()};
        outfit.object_ids=new Save.ObjectIdsList{object_id=kept.Select(i=>objects.Length==0?0ul:objects[i]).Append(0ul).ToArray()};
        outfit.layer_ids=new Save.LayerIdsList{layer_id=kept.Select(i=>layers.Length==0?0u:layers[i]).Append(layer).ToArray()};
    }
    public object ApexThumbnailOutfit(JsonElement request) {
        if(request.EnumerateObject().Count()!=7)throw new InvalidDataException("Exact thumbnail outfit request required.");
        var pieces=request.GetProperty("resource_tgi").GetString().Split(':');
        if(pieces.Length!=3)throw new InvalidDataException("Exact thumbnail CASP key required.");
        var tgi=new TGI(Convert.ToUInt32(pieces[0],16),Convert.ToUInt32(pieces[1],16),Convert.ToUInt64(pieces[2],16));
        // The upstream loader indexes CASPs with group zero, matching outfit
        // instance references. Resolve that map key, then bind the candidate
        // to its full original group and byte hash in the selected package.
        if(tgi.Type!=0x034AEECB||!GameTGIs.TryGetValue(new TGI(tgi.Type,0,tgi.Instance),out var source))throw new InvalidDataException("Thumbnail CASP absent from loaded package map.");
        var package=gamePackages[source];var entry=package.Find(r=>r.ResourceType==tgi.Type&&r.ResourceGroup==tgi.Group&&r.Instance==tgi.Instance);
        if(entry==null)throw new InvalidDataException("Thumbnail CASP source is absent.");
        using var input=package.GetResource(entry);using var raw=new MemoryStream();input.CopyTo(raw);
        var bytes=raw.ToArray();if(bytes.Length>1024*1024||Hash(bytes)!=request.GetProperty("resource_sha256").GetString())throw new InvalidDataException("Thumbnail effective CASP differs from catalog candidate.");
        using var reader=new BinaryReader(new MemoryStream(bytes));var casp=new CASP(reader);uint body=request.GetProperty("body_type").GetUInt32();
        if((uint)casp.BodyType!=body)throw new InvalidDataException("Thumbnail body type differs.");
        var outfits=Parse<Save.OutfitList>(Convert.FromBase64String(request.GetProperty("outfits_base64").GetString()));
        int n=request.GetProperty("outfit_index").GetInt32();if(n<0||n>=outfits.outfits.Count||outfits.outfits[n].outfit_id.ToString()!=request.GetProperty("outfit_id").GetString())throw new InvalidDataException("Thumbnail base outfit absent or changed.");
        ApexThumbnailPart(outfits.outfits[n],body,tgi.Instance,checked((uint)casp.SortLayer));
        using var output=new MemoryStream();Serializer.Serialize(output,outfits);
        return new{ok=true,outfits_base64=Convert.ToBase64String(output.ToArray()),resource_tgi=request.GetProperty("resource_tgi").GetString(),resource_sha256=Hash(bytes),body_type=body,disk_assets_written=false};
    }
    public object ApexAssemble(JsonElement request) {
        if(request.TryGetProperty("output",out _))throw new InvalidDataException("Preview assembly is memory-only; disk exports belong to the explicit debug CLI.");
        ApexReleaseImages();
        var assets=new Dictionary<string,byte[]>();
        string Png(string name,Image image) {using var stream=new MemoryStream();image.Save(stream,ImageFormat.Png);assets.Add(name,stream.ToArray());return name;}
        var sim = Parse<Save.SimData>(Convert.FromBase64String(request.GetProperty("native_sim").GetString()));
        if (sim.sim_id.ToString() != request.GetProperty("sim_id").GetString()) throw new InvalidDataException("Preview Sim identity differs.");
        var fields = request.GetProperty("fields");
        var outfits = Parse<Save.OutfitList>(Wire(fields, "__outfits__"));
        int index = request.GetProperty("outfit_index").GetInt32();
        if (index < 0 || index >= outfits.outfits.Count) throw new InvalidDataException("Preview outfit index is absent.");
        var outfit = outfits.outfits[index];
        if (outfit.outfit_id.ToString() != request.GetProperty("outfit_id").GetString()) throw new InvalidDataException("Preview outfit identity differs.");
        ApexRequirePreviewOutfit(outfit);
        // A detached copy selects one exact wardrobe. No game or save object
        // is mutated; the complete input payload remains the proof authority.
        outfits.outfits.Clear(); outfits.outfits.Add(outfit);
        sim.outfits = outfits; sim.current_outfit_type = outfit.category; sim.current_outfit_index = 0;
        sim.physique = fields.GetProperty("physique").GetProperty("value").GetString();
        sim.facial_attr = Wire(fields, "facial_attributes");
        sim.skin_tone = fields.GetProperty("skin_tone").GetProperty("value").GetUInt64();
        sim.skin_tone_val_shift = fields.GetProperty("skin_tone_val_shift").GetProperty("value").GetSingle();
        sim.genetic_data = Parse<Save.GeneticData>(Wire(fields,"genetic_data"));
        sim.pelt_layers = Parse<Save.PeltLayerDataList>(Wire(fields,"pelt_layers"));
        sim.custom_texture = fields.GetProperty("custom_texture").GetProperty("value").GetUInt64();
        var tattoos=fields.GetProperty("parts_custom_tattoos");
        if(tattoos.GetProperty("kind").GetString()!="mapping"||tattoos.GetProperty("value").GetArrayLength()>1024)
            throw new InvalidDataException("Exact bounded native tattoo mapping required.");
        sim.parts_custom_tattoos.Clear();
        var tattooRows=new HashSet<uint>();
        foreach(var pair in tattoos.GetProperty("value").EnumerateArray()){
            if(pair.GetArrayLength()!=2||pair[0].GetProperty("kind").GetString()!="value"||pair[1].GetProperty("kind").GetString()!="value")
                throw new InvalidDataException("Native tattoo field types differ.");
            uint body=pair[0].GetProperty("value").GetUInt32();ulong texture=pair[1].GetProperty("value").GetUInt64();
            if(!tattooRows.Add(body))throw new InvalidDataException("Duplicate native tattoo body type.");
            sim.parts_custom_tattoos.Add(new Save.SimPartCustomTattooData{body_type=body,texture_id=texture});
        }
        uint form = request.GetProperty("form").GetUInt32();
        uint visualForm = request.TryGetProperty("visual_form",out var visual) ? visual.GetUInt32() : form;
        if (visualForm != form && !(form == 32 && visualForm == 1))
            throw new InvalidDataException("Visual appearance policy differs from the selected owner.");
        sim.attributes ??= new Save.PersistableSimInfoAttributes();
        // Upstream composites painted textures through its tattoo tracker.
        // Supply only this selected form's mapping, never another form's.
        sim.attributes.tattoo_tracker=new Save.PersistableTattooTracker();
        foreach(var tattoo in sim.parts_custom_tattoos)if(tattoo.texture_id!=0)
            sim.attributes.tattoo_tracker.body_type_tattoo_data.Add(new Save.TattooData{body_type=tattoo.body_type,body_part_custom_texture=tattoo.texture_id,occult_type=visualForm});
        sim.attributes.occult_tracker = new Save.PersistableOccultTracker { occult_types=visualForm, current_occult_types=visualForm };
        if (visualForm != 1) sim.attributes.occult_tracker.occult_sim_infos.Add(new Save.PersistableOccultTracker.OccultSimData {
            occult_type=visualForm, physique=sim.physique, facial_attributes=sim.facial_attr,
            outfits=outfits, skin_tone=sim.skin_tone, skin_tone_val_shift=sim.skin_tone_val_shift, genetic_data=sim.genetic_data });
        worldNames = new Dictionary<ulong,string>();
        sims_listBox.SelectedIndexChanged -= sims_listBox_SelectedIndexChanged;
        sims_listBox.Items.Clear(); sims_listBox.Items.Add(new SimListing(sim)); sims_listBox.SelectedIndex=0;
        sims_listBox_SelectedIndexChanged(null, EventArgs.Empty);
        if (CurrentModel == null || !CurrentModel.Any(x => x != null)) throw new InvalidDataException("No assembled preview geometry.");
        var bones = currentRig.Bones.Select((b,i) => new {index=i,name=b.BoneName,hash=b.BoneHash,parent=b.ParentBoneIndex,
            position=b.WorldPosition.Coordinates,local_position=b.PositionVector.Coordinates,
            rotation=b.LocalRotation.Coordinates,scale=b.ScalingVector.Coordinates}).ToArray();
        if (bones.Length > 256) throw new InvalidDataException("Preview skeleton exceeds shader capacity.");
        var surfaces = new List<object>();
        void Surface(string name, GEOM[] meshes, Image texture, Image specular, bool transparent) {
            if (meshes == null || !meshes.Any(x => x != null)) return;
            if (texture == null) throw new InvalidDataException("Assembled " + name + " texture unavailable.");
            string image = Png(name + ".png",texture);
            string spec = null;
            if (specular != null) spec=Png(name+"-specular.png",specular);
            var parts = new List<object>();
            for (int slot=0;slot<meshes.Length;slot++) {
                GEOM mesh=meshes[slot]; if(mesh==null) continue;
                if (mesh.numberVertices <= 0 || mesh.numberVertices > 1000000 || mesh.numberFaces > 2000000) throw new InvalidDataException("Mesh bounds exceeded.");
                string file=name+"-"+slot+".mesh";
                using(var data=new MemoryStream()) {
                  using(var writer=new BinaryWriter(data,Encoding.UTF8,true)) {
                    writer.Write(Encoding.ASCII.GetBytes("APXMESH1")); writer.Write(mesh.numberVertices); writer.Write(mesh.numberFaces*3);
                    for(int v=0;v<mesh.numberVertices;v++) {
                        foreach(float f in mesh.getPosition(v)) writer.Write(f);
                        foreach(float f in mesh.getNormal(v)) writer.Write(f);
                        foreach(float f in mesh.getUV(v,0)) writer.Write(f);
                        var joints=mesh.hasBones?mesh.getBones(v):new byte[4];
                        var weights=mesh.hasBones?mesh.getBoneWeightsV5(v):new float[]{1,0,0,0};
                        if(weights==null) weights=mesh.getBoneWeights(v).Select(w=>w/255f).ToArray();
                        var mapped=new ushort[4];
                        for(int j=0;j<4;j++) {
                            int bone=mesh.hasBones&&joints[j]<mesh.BoneHashList.Length?currentRig.GetIndex(mesh.BoneHashList[joints[j]]):0;
                            if (bone<0 && weights[j]>0) throw new InvalidDataException("Mesh refers to an unresolved rig bone.");
                            mapped[j]=(ushort)Math.Max(0,bone); writer.Write(mapped[j]);
                        }
                        float sum=weights.Sum();
                        for(int j=0;j<4;j++) writer.Write(sum>0?weights[j]/sum:(j==0?1f:0f));
                    }
                    for(int face=0;face<mesh.numberFaces;face++) foreach(uint n in mesh.getFaceIndicesUint(face)) writer.Write(n);
                  }
                  assets.Add(file,data.ToArray());
                }
                parts.Add(new {body_type=slot,file,sha256=Hash(assets[file]),vertices=mesh.numberVertices,indices=mesh.numberFaces*3});
            }
            surfaces.Add(new {name,image,image_sha256=Hash(assets[image]),specular=spec,
                specular_sha256=spec==null?null:Hash(assets[spec]),transparent,parts});
        }
        Surface("body",CurrentModel,currentTexture,currentClothingSpecular,false);
        Surface("glass",GlassModel,currentGlassTexture,currentGlassSpecular,true);
        Surface("wings",WingsModel,currentWingsTexture,currentWingsSpecular,true);
        var animations=new List<object>();var animationErrors=new List<string>();
        ulong clipId=(uint)currentGender==8192?0xf156b0f88e200b17ul:0x2b4bf39b12c6e657ul;
        var clipKey=new TGI(0x6b20c4f3,0,clipId);
        try {
            if(GameTGIs.TryGetValue(clipKey,out uint pack)) {
                var entry=gamePackages[pack].Find(r=>r.ResourceType==clipKey.Type&&r.Instance==clipKey.Instance);
                if(entry!=null) {using var stream=gamePackages[pack].GetResource(entry);using var data=new MemoryStream();stream.CopyTo(data);
                    animations.Add(ApexClip.Decode(data.ToArray()));}
            }
            if(animations.Count==0)animationErrors.Add("Native CAS idle clip was not found.");
        } catch(Exception e) {animationErrors.Add(e.Message);}
        var modifierRows=new List<object>();var face=Parse<Save.BlobSimFacialCustomizationData>(sim.facial_attr);
        void Modifiers(int group,List<Save.BlobSimFacialCustomizationData.Modifier> entries) {
            if(entries==null)return;if(entries.Count>4096)throw new InvalidDataException("Modifier inventory exceeds bound.");
            for(int i=0;i<entries.Count;i++) {
                var entry=entries[i];var key=new TGI((uint)ResourceTypes.SimModifier,0,entry.key);string errors="";
                var resource=FetchGameSMOD(key,ref errors);
                var region=resource==null?"Unresolved modifier":resource.region.ToString().Replace('_',' ');
                var sub=resource==null||resource.subRegion.ToString()=="None"?"":" / "+resource.subRegion;
                modifierRows.Add(new {group,index=i,key=entry.key.ToString(),amount=entry.amount,
                    label=region+sub+" / "+entry.key.ToString("X16"),package=resource==null?null:Path.GetFileName(resource.package),
                    resource_tgi=key.ToString(),name_status="region / resource identity",resource_verified=resource!=null});
            }
        }
        Modifiers(2,face.face_modifiers);Modifiers(3,face.body_modifiers);Modifiers(4,face.aged_face_modifiers);Modifiers(5,face.aged_body_modifiers);
        var result=new {ok=true,schema=1,source="SimRipper-"+ApexWorkerVersion,sim_id=sim.sim_id.ToString(),form,
            outfit_id=outfit.outfit_id.ToString(),outfit_index=index,bones,surfaces,animations,modifiers=modifierRows,animation_errors=animationErrors,warnings=errorList,window_shown=false};
        string manifest=JsonSerializer.Serialize(result);
        if(assets.Values.Sum(x=>(long)x.Length)>64*1024*1024)throw new InvalidDataException("Assembled scene exceeds memory budget.");
        ApexReleaseImages();
        return new {ok=true,manifest_json=manifest,manifest_sha256=Hash(Encoding.UTF8.GetBytes(manifest)),
            assets=assets.ToDictionary(x=>x.Key,x=>Convert.ToBase64String(x.Value)),bones=bones.Length,
            surfaces=surfaces.Count,window_shown=false,disk_assets_written=false};
    }
    const string ApexWorkerVersion="862a32949e5156b371e2d2f83de4e37e0bb1afcc";
}
}
