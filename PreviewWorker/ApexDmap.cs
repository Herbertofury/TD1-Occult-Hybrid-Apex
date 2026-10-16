// SPDX-License-Identifier: GPL-3.0-or-later
// Bounded V9 deformer-map reader. The installed V9 resources add three header
// bytes and packed 11/11/10 position pixels; legacy V7 parsing mistakes those
// header bytes for dimensions and can attempt multi-gigabyte allocations.
using System;
using System.IO;

namespace TS4SimRipper {
public partial class DMap {
    byte[][] apexPixels;
    byte[] apexRobe;
    int apexBytes;

    void ApexReadModern(BinaryReader reader) {
        if(reader.BaseStream.Length>32*1024*1024)throw new InvalidDataException("Modern deformer exceeds bound.");
        doubledWidth=reader.ReadUInt32();height=reader.ReadUInt32();ageGender=reader.ReadUInt32();species=reader.ReadUInt32();
        physique=reader.ReadByte();shapeOrNormals=(ShapeOrNormals)reader.ReadByte();
        apexBytes=reader.ReadByte();byte reserved=reader.ReadByte(),format=reader.ReadByte();
        if((apexBytes!=3&&apexBytes!=4)||reserved!=0||format!=2)throw new InvalidDataException("Unsupported modern deformer pixel format.");
        minCol=reader.ReadUInt32();maxCol=reader.ReadUInt32();minRow=reader.ReadUInt32();maxRow=reader.ReadUInt32();
        robeChannel=(RobeChannel)reader.ReadByte();
        if((byte)robeChannel>2)throw new InvalidDataException("Unknown global deformer robe channel.");
        skinTightMinVal=reader.ReadSingle();skinTightDelta=reader.ReadSingle();
        if(robeChannel==RobeChannel.ROBECHANNEL_PRESENT){robeMinVal=reader.ReadSingle();robeDelta=reader.ReadSingle();}
        else {robeMinVal=skinTightMinVal;robeDelta=skinTightDelta;}
        if(!float.IsFinite(skinTightMinVal)||!float.IsFinite(skinTightDelta)||!float.IsFinite(robeMinVal)||!float.IsFinite(robeDelta)||skinTightDelta<0||robeDelta<0)
            throw new InvalidDataException("Non-finite deformer range.");
        totalBytes=reader.ReadInt32();
        if(totalBytes<0||totalBytes!=reader.BaseStream.Length-reader.BaseStream.Position)throw new InvalidDataException("Deformer data extent differs.");
        if(doubledWidth==0||doubledWidth%2!=0||Width>4096||height==0||height>4096||minCol>maxCol||minRow>maxRow||maxCol>=Width||maxRow>=height)
            throw new InvalidDataException("Deformer dimensions exceed bound.");
        int width=checked((int)(maxCol-minCol+1)),rows=checked((int)(maxRow-minRow+1));
        if((long)width*rows>4*1024*1024)throw new InvalidDataException("Deformer pixel budget exceeded.");
        apexPixels=new byte[totalBytes==0?0:rows][];apexRobe=new byte[apexPixels.Length];scanLines=new ScanLine[apexPixels.Length];
        for(int row=0;row<apexPixels.Length;row++){
            long start=reader.BaseStream.Position;int size=reader.ReadUInt16();byte compression=reader.ReadByte();
            long end=start+size;
            if(size<3||end>reader.BaseStream.Length)throw new InvalidDataException("Deformer row extent differs.");
            if(compression==2){if(size!=3)throw new InvalidDataException("Empty deformer row has extra bytes.");continue;}
            if(compression>1||size<4)throw new InvalidDataException("Unknown deformer compression.");
            byte robe=reader.ReadByte();if(robe>2)throw new InvalidDataException("Unknown deformer robe channel.");
            apexRobe[row]=robe;int stride=apexBytes*(robe==0?2:1);
            var pixels=new byte[checked(width*stride)];
            if(compression==0){
                if(end-reader.BaseStream.Position!=pixels.Length)throw new InvalidDataException("Uncompressed deformer row extent differs.");
                reader.BaseStream.ReadExactly(pixels);
            }else{
                byte count=reader.ReadByte();if(count<2||reader.BaseStream.Position+4*count>end)throw new InvalidDataException("Deformer RLE index extent differs.");
                var indexes=new ushort[count];var offsets=new ushort[count];
                for(int i=0;i<count;i++)indexes[i]=reader.ReadUInt16();
                for(int i=0;i<count;i++)offsets[i]=reader.ReadUInt16();
                int length=checked((int)(end-reader.BaseStream.Position));var encoded=reader.ReadBytes(length);
                if(length%(stride+1)!=0)throw new InvalidDataException("Deformer RLE packets truncated.");
                int runs=length/(stride+1),column=0;
                for(int run=0;run<runs;run++){
                    int at=run*(stride+1),repeat=encoded[at];
                    if(repeat==0||repeat>width-column)throw new InvalidDataException("Deformer RLE run exceeds its row.");
                    for(int n=0;n<repeat;n++)Buffer.BlockCopy(encoded,at+1,pixels,(column+n)*stride,stride);
                    column+=repeat;
                }
                if(column!=width)throw new InvalidDataException("Deformer RLE row is incomplete.");
                for(int i=0;i<count;i++)if(indexes[i]>=width||offsets[i]>=runs||(i>0&&(indexes[i]<indexes[i-1]||offsets[i]<offsets[i-1])))
                    throw new InvalidDataException("Deformer RLE index exceeds its packet inventory.");
            }
            if(reader.BaseStream.Position!=end)throw new InvalidDataException("Deformer row did not consume its extent.");
            apexPixels[row]=pixels;
        }
        if(reader.BaseStream.Position!=reader.BaseStream.Length)throw new InvalidDataException("Deformer has trailing rows.");
    }

    static float ApexComponent(uint value,int bits,float minimum,float delta) {
        return value==(1u<<(bits-1))?0f:(float)(minimum+value*(double)delta/((1u<<bits)-1));
    }

    Vector3 ApexPixel(byte[] data,int offset,float minimum,float delta) {
        if(apexBytes==3)return new Vector3(ApexComponent(data[offset],8,minimum,delta),ApexComponent(data[offset+1],8,minimum,delta),ApexComponent(data[offset+2],8,minimum,delta));
        uint pixel=BitConverter.ToUInt32(data,offset);
        return new Vector3(ApexComponent(pixel&2047,11,minimum,delta),ApexComponent((pixel>>11)&2047,11,minimum,delta),ApexComponent(pixel>>22,10,minimum,delta));
    }

    MorphMap ApexModernMorph() {
        int width=checked((int)(maxCol-minCol+1));int rows=apexPixels.Length;
        var skin=new Vector3[rows][];var robe=new Vector3[rows][];var present=new bool[rows];
        for(int y=0;y<rows;y++){
            skin[y]=new Vector3[width];robe[y]=new Vector3[width];var pixels=apexPixels[y];present[y]=pixels!=null&&apexRobe[y]==0;
            int stride=apexBytes*(present[y]?2:1);
            for(int x=0;x<width;x++){
                skin[y][x]=pixels==null?new Vector3():ApexPixel(pixels,x*stride,skinTightMinVal,skinTightDelta);
                robe[y][x]=pixels==null||apexRobe[y]==1?new Vector3():apexRobe[y]==2?new Vector3(skin[y][x]):ApexPixel(pixels,x*stride+apexBytes,robeMinVal,robeDelta);
            }
        }
        return new MorphMap(Width,height,shapeOrNormals,minCol,maxCol,minRow,maxRow,skin,robe,present,weight,AgeGender,package,instance,region);
    }
}
}
