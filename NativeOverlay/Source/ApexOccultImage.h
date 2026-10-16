// Installed DST5 icons: bounded shuffled BC3, decoded only on the worker.
// BC3: https://learn.microsoft.com/windows/win32/direct3d10/d3d10-graphics-programming-guide-resources-block-compression
#pragma once
#include "ApexResourceImage.h"

namespace td1::resource {
inline bool DecodeOccultImage(const std::string& raw,const Json& row,Pixels& pixels,std::string& reason) {
    pixels={};reason="Installed icon bytes or dimensions are invalid.";
    if(!row.is_object()||!Hash(row,"sha256")||raw.size()>128*1024||HashBytes(raw)!=ui::Scalar(row,"sha256"))return false;
    if(ui::Scalar(row,"format")=="png") {
        const Json binding={{"thumbnail",{{"status","resolved"},{"sha256",row["sha256"]},
            {"width",row.value("width",Json())},{"height",row.value("height",Json())}}}};
        return DecodeThumbnail(raw,binding,pixels,reason);
    }
    auto u32=[&](size_t offset){uint32_t result=0;std::memcpy(&result,raw.data()+offset,4);return result;};
    const bool shuffled=ui::Scalar(row,"format")=="dst5";
    if((!shuffled&&ui::Scalar(row,"format")!="dxt5")||raw.size()<128||std::memcmp(raw.data(),"DDS |\0\0\0",8)||
        std::memcmp(raw.data()+84,shuffled?"DST5":"DXT5",4)||u32(76)!=32||u32(28)>1)return false;
    const unsigned height=u32(12),width=u32(16);
    if(!width||!height||width>512||height>512||width%4||height%4||raw.size()!=128+size_t(width)*height||
        row.value("width",Json())!=width||row.value("height",Json())!=height)return false;
    const auto data=reinterpret_cast<const unsigned char*>(raw.data()+128);const size_t blocks=size_t(width)*height/16;
    pixels.width=width;pixels.height=height;pixels.rgba.resize(size_t(width)*height*4);
    for(size_t b=0;b<blocks;++b){
        const auto endpoints=data+(shuffled?b*2:b*16);
        unsigned alpha[8]={endpoints[0],endpoints[1]};
        if(alpha[0]>alpha[1])for(unsigned i=1;i<=6;++i)alpha[i+1]=((7-i)*alpha[0]+i*alpha[1])/7;
        else{for(unsigned i=1;i<=4;++i)alpha[i+1]=((5-i)*alpha[0]+i*alpha[1])/5;alpha[6]=0;alpha[7]=255;}
        const auto colors=data+(shuffled?blocks*2+b*4:b*16+8);const uint16_t a=uint16_t(colors[0])|uint16_t(colors[1])<<8,c=uint16_t(colors[2])|uint16_t(colors[3])<<8;
        unsigned rgb[4][3]={{unsigned(a>>11)*255/31,unsigned((a>>5)&63)*255/63,unsigned(a&31)*255/31},
            {unsigned(c>>11)*255/31,unsigned((c>>5)&63)*255/63,unsigned(c&31)*255/31}};
        for(unsigned channel=0;channel<3;++channel){rgb[2][channel]=(2*rgb[0][channel]+rgb[1][channel])/3;rgb[3][channel]=(rgb[0][channel]+2*rgb[1][channel])/3;}
        uint64_t ai=0;for(unsigned i=0;i<6;++i)ai|=uint64_t(data[(shuffled?blocks*6+b*6:b*16+2)+i])<<(8*i);
        uint32_t ci=0;std::memcpy(&ci,data+(shuffled?blocks*12+b*4:b*16+12),4);
        for(unsigned i=0;i<16;++i){const auto x=(b%(width/4))*4+i%4,y=(b/(width/4))*4+i/4;
            auto out=pixels.rgba.data()+(y*width+x)*4;const auto color=(ci>>(i*2))&3;
            for(unsigned channel=0;channel<3;++channel)out[channel]=static_cast<unsigned char>(rgb[color][channel]);
            out[3]=static_cast<unsigned char>(alpha[(ai>>(i*3))&7]);}
    }
    reason.clear();return true;
}
}
