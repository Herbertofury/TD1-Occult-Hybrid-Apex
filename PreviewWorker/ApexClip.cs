// SPDX-License-Identifier: GPL-3.0-or-later
// Bounded TS4 CLIP / embedded S3 curve decoder. Format inspected in the
// owner's installed s4mm 2.2.4-alpha and s4pe's ClipResource contract.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;

namespace TS4SimRipper {
internal static class ApexClip {
    internal static object Decode(byte[] bytes) {
        if (bytes.Length < 104 || bytes.Length > 16*1024*1024) throw new InvalidDataException("Clip size is invalid.");
        int start=-1;
        byte[] magic=Encoding.ASCII.GetBytes("_pilC3S_");
        for (int i=0;i<=bytes.Length-52;i++) if (bytes.AsSpan(i,8).SequenceEqual(magic)) {start=i;break;}
        if(start<0) throw new InvalidDataException("Clip codec is absent.");
        byte[] raw=bytes.AsSpan(start).ToArray();
        using var reader=new BinaryReader(new MemoryStream(raw));
        uint U(int p) { reader.BaseStream.Position=p; return reader.ReadUInt32(); }
        ushort H(int p) {reader.BaseStream.Position=p;return reader.ReadUInt16();}
        float F(int p) {reader.BaseStream.Position=p;float v=reader.ReadSingle();if(!float.IsFinite(v)) throw new InvalidDataException("Non-finite clip value.");return v;}
        int Offset(uint v) {if(v>raw.Length) throw new InvalidDataException("Clip offset leaves buffer.");return (int)v;}
        string Z(uint p) {int a=Offset(p),n=Array.IndexOf(raw,(byte)0,a);if(n<0||n-a>1024) throw new InvalidDataException("Invalid clip name.");return Encoding.Latin1.GetString(raw,a,n-a);}
        int count=checked((int)U(24)),tableCount=checked((int)U(28));
        if(count>2048||tableCount>1000000) throw new InvalidDataException("Clip curve bound exceeded.");
        int curves=Offset(U(32)),table=Offset(U(36));
        float duration=BitConverter.ToSingle(bytes,8),step=F(16);
        int frameCount=H(20);if(!float.IsFinite(duration)||duration<0||duration>3600||step<=0||step>1||frameCount==0) throw new InvalidDataException("Invalid clip timing.");
        if(curves+(long)count*20>raw.Length||table+(long)tableCount*4>raw.Length) throw new InvalidDataException("Truncated clip table.");
        var tracks=new List<object>();
        for(int c=0;c<count;c++) {
            int o=curves+c*20,p=Offset(U(o));uint key=U(o+4);float shift=F(o+8),scale=F(o+12);int frames=H(o+16),flags=raw[o+18],kind=raw[o+19];
            // Codec flag bit 3 belongs to the curve's mode, not packing.
            // Non-transform curves are bounded but ignored by a Sim rig.
            if(kind!=1&&kind!=2) continue;
            // Modern ChannelType F3_Zero/F4_QuaternionIdentity carries no
            // frame buffer. Treat these as explicit constant local channels.
            if(flags==11&&kind==1 || flags==17&&kind==2) {
                tracks.Add(new {key,kind,frames=new[]{new {frame=0,values=kind==1?new float[]{0,0,0}:new float[]{0,0,0,1}}}});continue;
            }
            int format=flags&7,packing=flags>>4,n=format==4?4:format==2?3:format==1?1:0;
            if(n==0||packing>1||frames>frameCount+1) throw new InvalidDataException("Unsupported clip curve encoding: flags="+flags+", kind="+kind);
            var keys=new List<object>();int previous=-1;
            for(int j=0;j<frames;j++) {
                int frame=H(p),sign=H(p+2);p+=4;
                if(frame<previous||frame>frameCount) throw new InvalidDataException("Unordered/out-of-range clip frame.");previous=frame;
                var v=new float[n];
                if(packing==1&&format==2) {uint packed=U(p);p+=4;for(int k=0;k<n;k++)v[k]=((packed>>(k*10))&1023)/1023f;}
                else for(int k=0;k<n;k++) {int h=H(p);p+=2;if(packing==0){if(h>=tableCount)throw new InvalidDataException("Clip float index is absent.");v[k]=F(table+h*4);}else v[k]=(h&4095)/4095f;}
                for(int k=0;k<n;k++){if((sign&(1<<k))!=0)v[k]=-v[k];v[k]=v[k]*scale+shift;if(!float.IsFinite(v[k]))throw new InvalidDataException("Invalid decoded curve.");}
                if(kind==1||kind==2) keys.Add(new {frame,values=v});
            }
            if(kind==1||kind==2) {if(n!=(kind==1?3:4))throw new InvalidDataException("Position/rotation dimensions differ.");tracks.Add(new {key,kind,frames=keys});}
        }
        return new {name=Z(U(40)),source_name=Z(U(44)),duration,frame_duration=step,frame_count=frameCount,tracks};
    }
}
}
