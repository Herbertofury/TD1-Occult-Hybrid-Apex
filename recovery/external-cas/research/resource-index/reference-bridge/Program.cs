// SPDX-License-Identifier: GPL-3.0-or-later
// Test bridge: links independently obtained TS4CAS Tools source at build time.
using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using Xmods.DataLib;
namespace System.Windows.Forms { }

class Program {
  static string Key(TGI key) => $"{key.Type:X8}:{key.Group:X8}:{key.Instance:X16}";
  static void Main(string[] args) {
    using var input = new MemoryStream();
    var stdin = Console.OpenStandardInput();
    byte[] buffer = new byte[8192]; int n;
    while ((n = stdin.Read(buffer, 0, buffer.Length)) > 0) {
      if (input.Length + n > 1024 * 1024) throw new InvalidDataException("input bound");
      input.Write(buffer, 0, n);
    }
    input.Position = 0;
    using var reader = new BinaryReader(input);
    if (args.Length > 0 && args[0] == "rigmat") {
      var rig = new RIG(reader);
      Console.Write(JsonSerializer.Serialize(rig.Bones.Select(b => new { local = b.LocalTransform.Values, global = b.GlobalTransform.Values }).ToArray()));
      return;
    }
    if (args.Length > 0 && args[0] == "rig") {
      var rig = new RIG(reader);
      Console.Write(JsonSerializer.Serialize(rig.Bones.Select(b => new {
        name = b.BoneName, hash = b.BoneHash, parentIndex = b.ParentBoneIndex,
        position = new[] { b.PositionVector.X, b.PositionVector.Y, b.PositionVector.Z },
        scale = new[] { b.ScalingVector.X, b.ScalingVector.Y, b.ScalingVector.Z }
      }).ToArray()));
      return;
    }
    if (args.Length > 0 && args[0] == "region") {
      var region = new RegionMap(reader);
      Console.Write(JsonSerializer.Serialize(Enumerable.Range(0, region.NumberRegions).Select(i => new {
        region = region.GetRegion(i), layer = region.GetLayer(i), replacement = region.GetIsReplacement(i),
        keys = region.GetTGIlist(i).Select(Key).ToArray()
      }).ToArray()));
      return;
    }
    var casp = new CASP(reader);
    var refs = casp.LinkList;
    var meshes = Enumerable.Range(0, 256).SelectMany(lod => casp.MeshParts(lod).Select(key => new { lod, key = Key(key) })).ToArray();
    Console.Write(JsonSerializer.Serialize(new {
      version = casp.Version, body = casp.BodyTypeNumeric, age = casp.AgeNumeric, gender = casp.GenderNumeric,
      species = casp.SpeciesNumeric, diffuse = Key(refs[casp.TextureIndex]), shadow = Key(refs[casp.ShadowIndex]),
      region = Key(refs[casp.RegionMapIndex]), normal = Key(refs[casp.NormalMapIndex]), specular = Key(refs[casp.SpecularIndex]), meshes
    }));
  }
}
