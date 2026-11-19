// Independent off-screen Sim renderer. Never reads or changes a game camera,
// Sim, outfit, clock, HWND, or input focus. Assets are immutable worker output.
#pragma once
#include "ApexResourceImage.h"
#include <d3d11_1.h>
#include "ApexPreviewVS.h"
#include "ApexPreviewPS.h"
#include <DirectXMath.h>
#include <wrl/client.h>
#include <functional>
#include <cmath>
#include <array>
#include <map>
#include <stdexcept>

namespace td1::preview {
using Microsoft::WRL::ComPtr;
using namespace DirectX;
using Json = ui::Json;
using ReadAsset = std::function<std::string(const std::string&, const std::string&, size_t)>;
struct Vertex { float position[3], normal[3], uv[2]; uint16_t joints[4]; float weights[4]; };
static_assert(sizeof(Vertex)==56);
struct Bone { std::string name; uint32_t hash=0; int parent=-1; XMFLOAT3 local{}, scale{1,1,1}; XMFLOAT4 rotation{0,0,0,1}; };
struct Frame { float at=0; XMFLOAT4 value{}; };
struct Curve { uint32_t hash=0; unsigned kind=0; std::vector<Frame> frames; };
struct Clip { std::string name; float duration=0, step=0; std::vector<Curve> curves; };
struct Mesh { int body=0; bool transparent=false; std::vector<Vertex> vertices; std::vector<uint32_t> indices; unsigned surface=0; };
struct Surface { resource::Pixels diffuse; };
struct Scene {
    std::string id, sim, outfit, warnings; unsigned form=0, outfitIndex=0;
    std::vector<Bone> bones; std::vector<Clip> clips; std::vector<Mesh> meshes; std::vector<Surface> surfaces;
    Json modifiers=Json::array();
    XMFLOAT3 minimum{10000,10000,10000}, maximum{-10000,-10000,-10000};
};
inline float Number(const Json& j) {
    if(!j.is_number()) throw std::runtime_error("Preview numeric type differs.");
    float f=j.get<float>();if(!std::isfinite(f)||std::abs(f)>10000)throw std::runtime_error("Invalid preview number.");return f;
}
inline void Vector(const Json& j,float* out,size_t n) {
    if(!j.is_array()||j.size()!=n)throw std::runtime_error("Preview vector dimensions differ.");
    for(size_t i=0;i<n;i++)out[i]=Number(j[i]);
}
inline std::string Asset(const ReadAsset& read,const Json& j,const char* name,const char* hash,size_t bound) {
    const auto file=ui::Scalar(j,name),digest=ui::Scalar(j,hash);
    if(file.empty()||file.size()>80||file.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789-.")!=std::string::npos||
        file.find("..")!=std::string::npos||!resource::Hex(digest,64))throw std::runtime_error("Invalid preview asset identity.");
    auto raw=read(file,digest,bound);
    if(raw.empty()||raw.size()>bound||resource::HashBytes(raw)!=digest)throw std::runtime_error("Preview asset SHA256 differs.");return raw;
}
inline resource::Pixels Png(const std::string& raw) {
    const HRESULT hr=CoInitializeEx(nullptr,COINIT_MULTITHREADED); resource::Pixels result;
    { ComPtr<IWICImagingFactory> factory; ComPtr<IWICStream> stream; ComPtr<IWICBitmapDecoder> decoder;
      ComPtr<IWICBitmapFrameDecode> frame;ComPtr<IWICFormatConverter> convert;UINT w=0,h=0,n=0;GUID kind{};
      if(FAILED(CoCreateInstance(CLSID_WICImagingFactory,nullptr,CLSCTX_INPROC_SERVER,IID_PPV_ARGS(&factory)))||
         FAILED(factory->CreateStream(&stream))||FAILED(stream->InitializeFromMemory(reinterpret_cast<BYTE*>(const_cast<char*>(raw.data())),static_cast<DWORD>(raw.size())))||
         FAILED(factory->CreateDecoderFromStream(stream.Get(),nullptr,WICDecodeMetadataCacheOnLoad,&decoder))||
         FAILED(decoder->GetContainerFormat(&kind))||kind!=GUID_ContainerFormatPng||FAILED(decoder->GetFrameCount(&n))||n!=1||
         FAILED(decoder->GetFrame(0,&frame))||FAILED(frame->GetSize(&w,&h))||w==0||h==0||w>4096||h>4096||
         FAILED(factory->CreateFormatConverter(&convert))||FAILED(convert->Initialize(frame.Get(),GUID_WICPixelFormat32bppRGBA,WICBitmapDitherTypeNone,nullptr,0,WICBitmapPaletteTypeCustom))) {
           if(SUCCEEDED(hr))CoUninitialize();throw std::runtime_error("Invalid bounded preview PNG.");
      }
      result.width=w;result.height=h;result.rgba.resize(size_t(w)*h*4);
      if(FAILED(convert->CopyPixels(nullptr,w*4,static_cast<UINT>(result.rgba.size()),result.rgba.data())))result={};
    }
    if(SUCCEEDED(hr))CoUninitialize();if(result.rgba.empty())throw std::runtime_error("Preview texture decode failed.");return result;
}
inline Scene Decode(const Json& j,const ReadAsset& read,const std::string& id) {
    if(!j.is_object()||j.value("schema",0)!=1||!j.value("ok",false)||!resource::Hex(id,64))throw std::runtime_error("Unknown preview scene.");
    Scene s;s.id=id;s.sim=ui::Scalar(j,"sim_id");s.outfit=ui::Scalar(j,"outfit_id");s.form=j.at("form").get<unsigned>();s.warnings=ui::Scalar(j,"warnings");
    if(!ui::CasInt(j.at("outfit_index"),0,1023))throw std::runtime_error("Preview outfit ordinal differs.");
    s.outfitIndex=j.at("outfit_index").get<unsigned>();
    if(s.sim.empty()||s.outfit.empty()||!s.form)throw std::runtime_error("Preview owner is absent.");
    const auto& bones=j.at("bones");if(!bones.is_array()||bones.empty()||bones.size()>256)throw std::runtime_error("Invalid rig size.");
    for(const auto& b:bones) {Bone bone;bone.name=ui::Scalar(b,"name");bone.hash=b.at("hash").get<uint32_t>();bone.parent=b.at("parent").get<int>();
      Vector(b.at("local_position"),&bone.local.x,3);Vector(b.at("rotation"),&bone.rotation.x,4);Vector(b.at("scale"),&bone.scale.x,3);
      const float q=bone.rotation.x*bone.rotation.x+bone.rotation.y*bone.rotation.y+bone.rotation.z*bone.rotation.z+bone.rotation.w*bone.rotation.w;
      if(q<.9f||q>1.1f||bone.name.size()>256||bone.parent<-1||bone.parent>=int(bones.size())||bone.parent==int(s.bones.size())||
         bone.scale.x<=0||bone.scale.y<=0||bone.scale.z<=0)throw std::runtime_error("Invalid bone transform.");s.bones.push_back(bone);
    }
    for(size_t i=0;i<s.bones.size();i++){int p=int(i);size_t hops=0;while(p>=0){if(++hops>s.bones.size())throw std::runtime_error("Cyclic rig.");p=s.bones[size_t(p)].parent;}}
    const auto& surfaces=j.at("surfaces");if(!surfaces.is_array()||surfaces.empty()||surfaces.size()>3)throw std::runtime_error("Invalid material groups.");
    size_t vertices=0,indices=0;
    for(const auto& surface:surfaces) {
      const unsigned sid=static_cast<unsigned>(s.surfaces.size());s.surfaces.push_back({Png(Asset(read,surface,"image","image_sha256",16*1024*1024))});
      const auto& parts=surface.at("parts");if(!parts.is_array()||parts.size()>256)throw std::runtime_error("Invalid mesh count.");
      for(const auto& part:parts) {
        auto raw=Asset(read,part,"file","sha256",32*1024*1024);if(raw.size()<16||raw.substr(0,8)!="APXMESH1")throw std::runtime_error("Invalid mesh header.");
        uint32_t n=0,m=0;std::memcpy(&n,raw.data()+8,4);std::memcpy(&m,raw.data()+12,4);
        vertices+=n;indices+=m;
        if(n==0||m==0||m%3||vertices>1000000||indices>6000000||16ull+n*56ull+m*4ull!=raw.size())throw std::runtime_error("Invalid mesh extent.");
        Mesh mesh;mesh.body=part.at("body_type").get<int>();mesh.surface=sid;mesh.transparent=surface.at("transparent").get<bool>();
        mesh.vertices.resize(n);mesh.indices.resize(m);std::memcpy(mesh.vertices.data(),raw.data()+16,n*56ull);std::memcpy(mesh.indices.data(),raw.data()+16+n*56ull,m*4ull);
        for(const auto& v:mesh.vertices) {
          float total=0;for(int k=0;k<3;k++)if(!std::isfinite(v.position[k])||std::abs(v.position[k])>100||!std::isfinite(v.normal[k]))throw std::runtime_error("Invalid vertex.");
          for(int k=0;k<2;k++)if(!std::isfinite(v.uv[k])||std::abs(v.uv[k])>100)throw std::runtime_error("Invalid UV.");
          for(int k=0;k<4;k++){if(v.joints[k]>=s.bones.size()||!std::isfinite(v.weights[k])||v.weights[k]<0||v.weights[k]>1)throw std::runtime_error("Invalid skin weights.");total+=v.weights[k];}
          if(std::abs(total-1)>.002f)throw std::runtime_error("Skin weights do not sum to one.");
          s.minimum.x=std::min(s.minimum.x,v.position[0]);s.minimum.y=std::min(s.minimum.y,v.position[1]);s.minimum.z=std::min(s.minimum.z,v.position[2]);
          s.maximum.x=std::max(s.maximum.x,v.position[0]);s.maximum.y=std::max(s.maximum.y,v.position[1]);s.maximum.z=std::max(s.maximum.z,v.position[2]);
        }
        for(auto i:mesh.indices)if(i>=n)throw std::runtime_error("Mesh index leaves vertices.");s.meshes.push_back(std::move(mesh));
      }
    }
    if(s.meshes.empty())throw std::runtime_error("Empty preview geometry.");
    if(j.contains("modifiers")) {
      if(!j["modifiers"].is_array()||j["modifiers"].size()>16384)throw std::runtime_error("Modifier metadata bound exceeded.");
      for(const auto& row:j["modifiers"]){if(!row.is_object()||!ui::CasInt(row.value("group",Json()),2,5)||!ui::CasInt(row.value("index",Json()),0,4095)||ui::Scalar(row,"key").empty()||ui::Scalar(row,"key").size()>20||ui::Scalar(row,"label").size()>2048||ui::Scalar(row,"package").size()>8192||!row.contains("amount")||!row["amount"].is_number()||!std::isfinite(row["amount"].get<float>()))throw std::runtime_error("Invalid modifier metadata.");}
      s.modifiers=j["modifiers"];
    }
    if(j.contains("animations"))for(const auto& a:j["animations"]) {
      if(s.clips.size()>=32)throw std::runtime_error("Too many preview clips.");Clip clip;clip.name=ui::Scalar(a,"name");clip.duration=Number(a.at("duration"));clip.step=Number(a.at("frame_duration"));
      if(clip.duration<=0||clip.step<=0||clip.name.size()>1024)throw std::runtime_error("Invalid clip timing.");
      size_t count=0;for(const auto& t:a.at("tracks")){if(clip.curves.size()>=2048)throw std::runtime_error("Too many curves.");Curve c;c.hash=t.at("key").get<uint32_t>();c.kind=t.at("kind").get<unsigned>();
        if(c.kind!=1&&c.kind!=2)throw std::runtime_error("Unknown curve kind.");float previous=-1;
        for(const auto& f:t.at("frames")){if(++count>200000)throw std::runtime_error("Too many animation keys.");Frame frame;frame.at=Number(f.at("frame"))*clip.step;Vector(f.at("values"),&frame.value.x,c.kind==1?3:4);
          if(frame.at<previous||frame.at>clip.duration+clip.step*2)throw std::runtime_error("Invalid animation key order.");previous=frame.at;c.frames.push_back(frame);}
        if(!c.frames.empty())clip.curves.push_back(std::move(c));
      }s.clips.push_back(std::move(clip));
    }
    return s;
}
struct View {
    float yaw=0,pitch=0,distance=3.3f,height=1,pan=0,panDepth=0,roll=0;
    float fov=35,orthoScale=2.2f,time=0,speed=1,exposure=1;
    int clip=0,body=-1; bool playing=true,autoRotate=false,orthographic=false,blenderControls=true;
};
inline XMVECTOR Sample(const Curve& c,float time) {
    if(time<=c.frames.front().at)return XMLoadFloat4(&c.frames.front().value);
    auto next=std::upper_bound(c.frames.begin(),c.frames.end(),time,[](float t,const Frame& f){return t<f.at;});
    if(next==c.frames.end())return XMLoadFloat4(&c.frames.back().value);const auto& left=*(next-1);
    const float blend=(time-left.at)/std::max(.00001f,next->at-left.at);
    return c.kind==2?XMQuaternionSlerp(XMQuaternionNormalize(XMLoadFloat4(&left.value)),XMQuaternionNormalize(XMLoadFloat4(&next->value)),blend):XMVectorLerp(XMLoadFloat4(&left.value),XMLoadFloat4(&next->value),blend);
}
inline std::vector<XMMATRIX> Matrices(const Scene& s,const Clip* clip,float time) {
    std::vector<XMMATRIX> local(s.bones.size()),world(s.bones.size());std::vector<bool> ready(s.bones.size(),false);
    for(size_t i=0;i<s.bones.size();i++){const auto& b=s.bones[i];XMVECTOR p=XMLoadFloat3(&b.local),q=XMQuaternionNormalize(XMLoadFloat4(&b.rotation));
      if(clip)for(const auto& c:clip->curves)if(c.hash==b.hash){if(c.kind==1)p=Sample(c,time);else q=Sample(c,time);}
      local[i]=XMMatrixScaling(b.scale.x,b.scale.y,b.scale.z)*XMMatrixRotationQuaternion(q)*XMMatrixTranslationFromVector(p);
    }
    std::function<XMMATRIX(size_t)> build=[&](size_t i){if(!ready[i]){world[i]=s.bones[i].parent<0?local[i]:local[i]*build(size_t(s.bones[i].parent));ready[i]=true;}return world[i];};
    for(size_t i=0;i<s.bones.size();i++)build(i);return world;
}
inline void Check(HRESULT hr,const char* why){if(FAILED(hr))throw std::runtime_error(why);}
class Renderer {
    struct GpuMesh {ComPtr<ID3D11Buffer> vertex,index;unsigned count=0,surface=0;int body=0;bool transparent=false;};
    ComPtr<ID3D11Device> device;ComPtr<ID3D11VertexShader> vs;ComPtr<ID3D11PixelShader> ps;ComPtr<ID3D11InputLayout> layout;
    ComPtr<ID3D11Device1> isolatedDevice;ComPtr<ID3DDeviceContextState> cleanState;
    ComPtr<ID3D11Buffer> constants;ComPtr<ID3D11SamplerState> sampler;ComPtr<ID3D11RasterizerState> raster;
    ComPtr<ID3D11DepthStencilState> depth,glassDepth;ComPtr<ID3D11BlendState> blend;
    ComPtr<ID3D11Texture2D> target,depthTarget;ComPtr<ID3D11RenderTargetView> rtv;ComPtr<ID3D11DepthStencilView> dsv;ComPtr<ID3D11ShaderResourceView> srv;
    std::vector<GpuMesh> meshes;std::vector<ComPtr<ID3D11ShaderResourceView>> textures;std::vector<XMMATRIX> bind;
    std::map<int,std::pair<XMFLOAT3,XMFLOAT3>> partBounds;
    unsigned width=0,height=0;
    struct Constants { XMFLOAT4X4 view,joints[256];XMFLOAT4 light; };
public:
    Scene scene; View view;uint64_t frames=0,pipelineBuilds=0,pipelineReuses=0;
    ID3D11ShaderResourceView* Texture()const{return srv.Get();}
    ID3D11Texture2D* Target()const{return target.Get();}
    void Reset(){*this=Renderer();}
    void Preset(View& next,const std::string& name,int selectedBody=-1) const {
      if(name=="reset"){next.fov=35;next.orthographic=false;}
      if(name=="front"||name=="back"||name=="left"||name=="right"||name=="top") {
        next.yaw=name=="back"?XM_PI:name=="left"?-XM_PIDIV2:name=="right"?XM_PIDIV2:0;
        next.pitch=name=="top"?1.55f:0;next.roll=0;next.autoRotate=false;return;
      }
      auto minimum=scene.minimum,maximum=scene.maximum;
      if(name=="selected") {
        auto found=partBounds.find(selectedBody);if(found==partBounds.end())throw std::runtime_error("Selected category has no rendered geometry.");
        minimum=found->second.first;maximum=found->second.second;
      } else if(name=="face") {
        float head=maximum.y-.14f;
        const auto matrices=Matrices(scene,nullptr,0);
        for(size_t i=0;i<scene.bones.size();++i)if(scene.bones[i].name=="b__Head__"){XMFLOAT3 point;XMStoreFloat3(&point,matrices[i].r[3]);head=point.y+.08f;break;}
        minimum={-.22f,head-.23f,-.22f};maximum={.22f,head+.23f,.22f};
      } else if(name!="body"&&name!="reset")throw std::runtime_error("Unknown camera preset.");
      next.pan=(minimum.x+maximum.x)*.5f;next.height=(minimum.y+maximum.y)*.5f;next.panDepth=(minimum.z+maximum.z)*.5f;
      const float size=std::max({maximum.x-minimum.x,maximum.y-minimum.y,maximum.z-minimum.z,.1f});
      next.orthoScale=std::clamp(size*1.18f,.05f,30.f);
      next.distance=std::clamp(next.orthoScale*.5f/std::tan(XMConvertToRadians(next.fov)*.5f),.1f,30.f);
      next.body=-1;
      if(name=="reset"){next.yaw=next.pitch=next.roll=0;next.autoRotate=false;next.fov=35;next.orthographic=false;}
    }
    void Pan(float right,float up) {
      const XMVECTOR direction=XMVectorSet(std::sin(view.yaw)*std::cos(view.pitch),std::sin(view.pitch),std::cos(view.yaw)*std::cos(view.pitch),0);
      const auto upAxis=XMVector3TransformNormal(XMVectorSet(0,1,0,0),XMMatrixRotationAxis(direction,view.roll));
      const auto cameraRight=XMVector3Normalize(XMVector3Cross(upAxis,direction));
      const auto cameraUp=XMVector3Normalize(XMVector3Cross(direction,cameraRight));
      const auto delta=cameraRight*right+cameraUp*up;XMFLOAT3 values;XMStoreFloat3(&values,delta);
      view.pan=std::clamp(view.pan+values.x,-30.f,30.f);view.height=std::clamp(view.height+values.y,-30.f,30.f);view.panDepth=std::clamp(view.panDepth+values.z,-30.f,30.f);
    }
    void Load(ID3D11Device* d,Scene value) {
      Renderer next;next.device=d;next.scene=std::move(value);next.bind=Matrices(next.scene,nullptr,0);
      Check(next.device.As(&next.isolatedDevice),"Preview requires DX11.1 state isolation.");
      const D3D_FEATURE_LEVEL feature=d->GetFeatureLevel();Check(next.isolatedDevice->CreateDeviceContextState(0,&feature,1,D3D11_SDK_VERSION,__uuidof(ID3D11Device),nullptr,&next.cleanState),"Preview isolated state failed.");
      for(auto& m:next.bind)m=XMMatrixInverse(nullptr,m);
      next.pipelineBuilds=pipelineBuilds;next.pipelineReuses=pipelineReuses;
      if(device.Get()==d && vs && ps && layout) {
        // Immutable shaders/layout have no Sim or scene identity. Reuse them
        // on this exact live device; don't ask the driver to rebuild a shader
        // pipeline whenever the player equips another CAS part or form.
        next.vs=vs;next.ps=ps;next.layout=layout;++next.pipelineReuses;
      } else {
        Check(d->CreateVertexShader(apex_preview_vs,sizeof(apex_preview_vs),nullptr,&next.vs),"Preview VS creation failed.");
        Check(d->CreatePixelShader(apex_preview_ps,sizeof(apex_preview_ps),nullptr,&next.ps),"Preview PS creation failed.");
        D3D11_INPUT_ELEMENT_DESC elements[]={{"POSITION",0,DXGI_FORMAT_R32G32B32_FLOAT,0,0,D3D11_INPUT_PER_VERTEX_DATA,0},{"NORMAL",0,DXGI_FORMAT_R32G32B32_FLOAT,0,12,D3D11_INPUT_PER_VERTEX_DATA,0},{"TEXCOORD",0,DXGI_FORMAT_R32G32_FLOAT,0,24,D3D11_INPUT_PER_VERTEX_DATA,0},{"BLENDINDICES",0,DXGI_FORMAT_R16G16B16A16_UINT,0,32,D3D11_INPUT_PER_VERTEX_DATA,0},{"BLENDWEIGHT",0,DXGI_FORMAT_R32G32B32A32_FLOAT,0,40,D3D11_INPUT_PER_VERTEX_DATA,0}};
        Check(d->CreateInputLayout(elements,5,apex_preview_vs,sizeof(apex_preview_vs),&next.layout),"Preview vertex layout failed.");
        ++next.pipelineBuilds;
      }
      D3D11_BUFFER_DESC cb{};cb.ByteWidth=sizeof(Constants);cb.Usage=D3D11_USAGE_DEFAULT;cb.BindFlags=D3D11_BIND_CONSTANT_BUFFER;Check(d->CreateBuffer(&cb,nullptr,&next.constants),"Preview constants failed.");
      D3D11_SAMPLER_DESC sd{};sd.Filter=D3D11_FILTER_MIN_MAG_MIP_LINEAR;sd.AddressU=sd.AddressV=sd.AddressW=D3D11_TEXTURE_ADDRESS_WRAP;sd.MaxLOD=D3D11_FLOAT32_MAX;Check(d->CreateSamplerState(&sd,&next.sampler),"Preview sampler failed.");
      D3D11_RASTERIZER_DESC rd{};rd.FillMode=D3D11_FILL_SOLID;rd.CullMode=D3D11_CULL_NONE;rd.DepthClipEnable=TRUE;Check(d->CreateRasterizerState(&rd,&next.raster),"Preview raster failed.");
      D3D11_DEPTH_STENCIL_DESC dd{};dd.DepthEnable=TRUE;dd.DepthWriteMask=D3D11_DEPTH_WRITE_MASK_ALL;dd.DepthFunc=D3D11_COMPARISON_LESS_EQUAL;Check(d->CreateDepthStencilState(&dd,&next.depth),"Preview depth failed.");dd.DepthWriteMask=D3D11_DEPTH_WRITE_MASK_ZERO;Check(d->CreateDepthStencilState(&dd,&next.glassDepth),"Preview glass depth failed.");
      D3D11_BLEND_DESC bd{};auto& b=bd.RenderTarget[0];b.BlendEnable=TRUE;b.SrcBlend=D3D11_BLEND_SRC_ALPHA;b.DestBlend=D3D11_BLEND_INV_SRC_ALPHA;b.BlendOp=D3D11_BLEND_OP_ADD;b.SrcBlendAlpha=D3D11_BLEND_ONE;b.DestBlendAlpha=D3D11_BLEND_INV_SRC_ALPHA;b.BlendOpAlpha=D3D11_BLEND_OP_ADD;b.RenderTargetWriteMask=D3D11_COLOR_WRITE_ENABLE_ALL;Check(d->CreateBlendState(&bd,&next.blend),"Preview blending failed.");
      for(const auto& surf:next.scene.surfaces){D3D11_TEXTURE2D_DESC td{};td.Width=surf.diffuse.width;td.Height=surf.diffuse.height;td.MipLevels=td.ArraySize=1;td.Format=DXGI_FORMAT_R8G8B8A8_UNORM;td.SampleDesc.Count=1;td.Usage=D3D11_USAGE_IMMUTABLE;td.BindFlags=D3D11_BIND_SHADER_RESOURCE;
        D3D11_SUBRESOURCE_DATA init{surf.diffuse.rgba.data(),td.Width*4,0};ComPtr<ID3D11Texture2D> tex;ComPtr<ID3D11ShaderResourceView> image;Check(d->CreateTexture2D(&td,&init,&tex),"Preview diffuse upload failed.");Check(d->CreateShaderResourceView(tex.Get(),nullptr,&image),"Preview diffuse view failed.");next.textures.push_back(image);}
      for(const auto& mesh:next.scene.meshes){GpuMesh gpu;gpu.count=static_cast<unsigned>(mesh.indices.size());gpu.body=mesh.body;gpu.surface=mesh.surface;gpu.transparent=mesh.transparent;D3D11_BUFFER_DESC vb{};vb.ByteWidth=static_cast<UINT>(mesh.vertices.size()*sizeof(Vertex));vb.Usage=D3D11_USAGE_IMMUTABLE;vb.BindFlags=D3D11_BIND_VERTEX_BUFFER;D3D11_SUBRESOURCE_DATA v{mesh.vertices.data(),0,0};Check(d->CreateBuffer(&vb,&v,&gpu.vertex),"Preview vertex upload failed.");vb.ByteWidth=static_cast<UINT>(mesh.indices.size()*4);vb.BindFlags=D3D11_BIND_INDEX_BUFFER;v.pSysMem=mesh.indices.data();Check(d->CreateBuffer(&vb,&v,&gpu.index),"Preview index upload failed.");next.meshes.push_back(std::move(gpu));}
      for(const auto& mesh:next.scene.meshes)for(const auto& v:mesh.vertices) {
        const XMFLOAT3 point{v.position[0],v.position[1],v.position[2]};
        auto inserted=next.partBounds.emplace(mesh.body,std::make_pair(point,point));
        auto& bounds=inserted.first->second;
        bounds.first.x=std::min(bounds.first.x,point.x);bounds.first.y=std::min(bounds.first.y,point.y);bounds.first.z=std::min(bounds.first.z,point.z);
        bounds.second.x=std::max(bounds.second.x,point.x);bounds.second.y=std::max(bounds.second.y,point.y);bounds.second.z=std::max(bounds.second.z,point.z);
      }
      // Only one selected Sim owns GPU assets. Drop the decoded CPU copies
      // after upload; the broker's separate byte-bounded LRU owns reuse.
      for(auto& surface:next.scene.surfaces)std::vector<uint8_t>().swap(surface.diffuse.rgba);
      for(auto& mesh:next.scene.meshes){std::vector<Vertex>().swap(mesh.vertices);std::vector<uint32_t>().swap(mesh.indices);}
      next.Preset(next.view,"body");*this=std::move(next);
    }
    void Control(const Json& values) {
      if(!values.is_object()||values.empty())throw std::runtime_error("Exact preview view controls required.");
      View next=view;
      int focusBody=next.body;
      if(values.contains("focus_body_type")){const auto& body=values.at("focus_body_type");if(!ui::CasInt(body,0,65535)||!values.contains("preset")||values.at("preset")!="selected")throw std::runtime_error("Exact selected-part framing required.");focusBody=body.get<int>();}
      if(values.contains("preset")){if(!values.at("preset").is_string())throw std::runtime_error("Named camera preset required.");Preset(next,values.at("preset").get<std::string>(),focusBody);}
      for(auto it=values.begin();it!=values.end();++it){const auto& key=it.key();const auto& value=it.value();
        auto number=[&](float low,float high){if(!value.is_number())throw std::runtime_error("Numeric preview control required.");float n=value.get<float>();if(!std::isfinite(n)||n<low||n>high)throw std::runtime_error("Preview control exceeds range.");return n;};
        auto boolean=[&](){if(!value.is_boolean())throw std::runtime_error("Boolean preview control required.");return value.get<bool>();};
        if(key=="yaw")next.yaw=number(-100,100);else if(key=="pitch")next.pitch=number(-1.55f,1.55f);
        else if(key=="distance")next.distance=number(.1f,30);else if(key=="height")next.height=number(-30,30);
        else if(key=="pan")next.pan=number(-30,30);else if(key=="pan_depth")next.panDepth=number(-30,30);
        else if(key=="roll")next.roll=number(-XM_PI,XM_PI);else if(key=="fov")next.fov=number(10,90);
        else if(key=="ortho_scale")next.orthoScale=number(.05f,30);else if(key=="speed")next.speed=number(.1f,2);
        else if(key=="projection"){if(value!="perspective"&&value!="orthographic")throw std::runtime_error("Unknown camera projection.");next.orthographic=value=="orthographic";}
        else if(key=="controls"){if(value!="blender"&&value!="simple")throw std::runtime_error("Unknown camera controls.");next.blenderControls=value=="blender";}
        else if(key=="exposure")next.exposure=number(.5f,1.8f);else if(key=="playing")next.playing=boolean();
        else if(key=="turntable")next.autoRotate=boolean();
        else if(key=="clip"){if(!ui::CasInt(value,-1,int(scene.clips.size())-1))throw std::runtime_error("Unknown preview clip.");next.clip=value.get<int>();next.time=0;}
        else if(key=="body_type"){if(!ui::CasInt(value,-1,65535))throw std::runtime_error("Invalid preview body type.");next.body=value.get<int>();}
        else if(key=="time"||key=="preset"||key=="focus_body_type"){} // Validate after selecting the exact clip.
        else throw std::runtime_error("Unknown preview view control.");
      }
      if(values.contains("time")){const auto& n=values.at("time");const float maximum=next.clip>=0?scene.clips[size_t(next.clip)].duration:0;
        if(!n.is_number()||!std::isfinite(n.get<float>())||n.get<float>()<0||n.get<float>()>maximum)throw std::runtime_error("Preview time exceeds clip.");next.time=n.get<float>();}
      view=next; // A malformed field never partially changes another control.
    }
    void Render(ID3D11DeviceContext* context,unsigned w,unsigned h,float dt) {
      if(!device||w<16||h<16||w>2048||h>2048)return;
      if(w!=width||h!=height){target.Reset();rtv.Reset();srv.Reset();depthTarget.Reset();dsv.Reset();width=w;height=h;
        D3D11_TEXTURE2D_DESC td{};td.Width=w;td.Height=h;td.MipLevels=td.ArraySize=1;td.Format=DXGI_FORMAT_R8G8B8A8_UNORM;td.SampleDesc.Count=1;td.BindFlags=D3D11_BIND_RENDER_TARGET|D3D11_BIND_SHADER_RESOURCE;Check(device->CreateTexture2D(&td,nullptr,&target),"Preview target failed.");Check(device->CreateRenderTargetView(target.Get(),nullptr,&rtv),"Preview RTV failed.");Check(device->CreateShaderResourceView(target.Get(),nullptr,&srv),"Preview SRV failed.");td.Format=DXGI_FORMAT_D24_UNORM_S8_UINT;td.BindFlags=D3D11_BIND_DEPTH_STENCIL;Check(device->CreateTexture2D(&td,nullptr,&depthTarget),"Preview depth target failed.");Check(device->CreateDepthStencilView(depthTarget.Get(),nullptr,&dsv),"Preview DSV failed.");}
      // SwapDeviceContextState preserves every pipeline stage, resource and
      // UAV binding, including stages unused by this renderer. No partial
      // hand-written save/restore leaks into the game or ImGui draw pass.
      ComPtr<ID3D11DeviceContext1> c1;ComPtr<ID3DDeviceContextState> previous;
      Check(context->QueryInterface(IID_PPV_ARGS(&c1)),"Preview context isolation unavailable.");c1->SwapDeviceContextState(cleanState.Get(),&previous);
      struct Restore {ID3D11DeviceContext1* c;ID3DDeviceContextState* state;~Restore(){c->SwapDeviceContextState(state,nullptr);}} restore{c1.Get(),previous.Get()};
      const Clip* clip=view.clip>=0&&view.clip<int(scene.clips.size())?&scene.clips[size_t(view.clip)]:nullptr;
      if(clip&&view.playing)view.time=std::fmod(view.time+std::clamp(dt,0.f,.1f)*view.speed,clip->duration);
      if(view.autoRotate)view.yaw+=std::clamp(dt,0.f,.1f)*.25f;
      auto bones=Matrices(scene,clip,std::max(0.f,view.time));Constants cb{};
      for(size_t i=0;i<256;i++)XMStoreFloat4x4(&cb.joints[i],i<bones.size()?bind[i]*bones[i]:XMMatrixIdentity());
      view.distance=std::clamp(view.distance,.1f,30.f);view.pitch=std::clamp(view.pitch,-1.55f,1.55f);
      const XMVECTOR center=XMVectorSet(view.pan,view.height,view.panDepth,1),direction=XMVectorSet(std::sin(view.yaw)*std::cos(view.pitch),std::sin(view.pitch),std::cos(view.yaw)*std::cos(view.pitch),0),eye=center+direction*view.distance;
      const auto cameraUp=XMVector3TransformNormal(XMVectorSet(0,1,0,0),XMMatrixRotationAxis(direction,view.roll));
      const auto projection=view.orthographic?XMMatrixOrthographicRH(view.orthoScale*float(w)/h,view.orthoScale,.01f,100):XMMatrixPerspectiveFovRH(XMConvertToRadians(view.fov),float(w)/h,.01f,100);
      XMStoreFloat4x4(&cb.view,XMMatrixLookAtRH(eye,center,cameraUp)*projection);cb.light=XMFLOAT4(view.exposure,0,0,0);
      context->UpdateSubresource(constants.Get(),0,nullptr,&cb,0,0);
      const float bg[]={.035f,.048f,.065f,1};context->ClearRenderTargetView(rtv.Get(),bg);context->ClearDepthStencilView(dsv.Get(),D3D11_CLEAR_DEPTH,1,0);
      ID3D11RenderTargetView* rt=rtv.Get();context->OMSetRenderTargets(1,&rt,dsv.Get());D3D11_VIEWPORT vp{0,0,float(w),float(h),0,1};context->RSSetViewports(1,&vp);context->RSSetState(raster.Get());
      context->IASetInputLayout(layout.Get());context->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);context->VSSetShader(vs.Get(),nullptr,0);context->PSSetShader(ps.Get(),nullptr,0);ID3D11Buffer* buffer=constants.Get();context->VSSetConstantBuffers(0,1,&buffer);context->PSSetConstantBuffers(0,1,&buffer);ID3D11SamplerState* sm=sampler.Get();context->PSSetSamplers(0,1,&sm);
      const float factor[]={0,0,0,0};context->OMSetBlendState(blend.Get(),factor,0xffffffff);
      for(const auto& mesh:meshes){if(view.body>=0&&view.body!=mesh.body)continue;context->OMSetDepthStencilState(mesh.transparent?glassDepth.Get():depth.Get(),0);ID3D11Buffer* v=mesh.vertex.Get();UINT stride=56,offset=0;context->IASetVertexBuffers(0,1,&v,&stride,&offset);context->IASetIndexBuffer(mesh.index.Get(),DXGI_FORMAT_R32_UINT,0);ID3D11ShaderResourceView* t=textures[mesh.surface].Get();context->PSSetShaderResources(0,1,&t);context->DrawIndexed(mesh.count,0,0);}
      ++frames;
    }
};
}
