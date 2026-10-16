#include "ApexSimPreview.h"
#include <filesystem>
#include <fstream>
#include <iostream>
using namespace td1;
static std::string Read(const std::filesystem::path& path,size_t max) {
    if(std::filesystem::file_size(path)>max)throw std::runtime_error("File bound exceeded.");
    std::ifstream f(path,std::ios::binary);if(!f)throw std::runtime_error("File unavailable.");return std::string(std::istreambuf_iterator<char>(f),{});
}
static std::string Capture(ID3D11Device* device,ID3D11DeviceContext* context,ID3D11Texture2D* target,const std::filesystem::path& path={}) {
    D3D11_TEXTURE2D_DESC desc{};target->GetDesc(&desc);desc.Usage=D3D11_USAGE_STAGING;desc.BindFlags=0;desc.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
    preview::ComPtr<ID3D11Texture2D> staging;preview::Check(device->CreateTexture2D(&desc,nullptr,&staging),"Staging failed.");context->CopyResource(staging.Get(),target);
    D3D11_MAPPED_SUBRESOURCE mapped{};preview::Check(context->Map(staging.Get(),0,D3D11_MAP_READ,0,&mapped),"Readback failed.");
    std::string pixels(size_t(desc.Width)*desc.Height*4,'\0');for(UINT y=0;y<desc.Height;y++)std::memcpy(pixels.data()+size_t(y)*desc.Width*4,static_cast<char*>(mapped.pData)+size_t(y)*mapped.RowPitch,desc.Width*4);context->Unmap(staging.Get(),0);
    if(!path.empty()){
      preview::ComPtr<IWICImagingFactory> factory;preview::ComPtr<IWICStream> stream;preview::ComPtr<IWICBitmapEncoder> encoder;preview::ComPtr<IWICBitmapFrameEncode> frame;preview::ComPtr<IPropertyBag2> options;
      preview::Check(CoCreateInstance(CLSID_WICImagingFactory,nullptr,CLSCTX_INPROC_SERVER,IID_PPV_ARGS(&factory)),"WIC failed.");preview::Check(factory->CreateStream(&stream),"Output stream failed.");preview::Check(stream->InitializeFromFilename(path.c_str(),GENERIC_WRITE),"Output path failed.");preview::Check(factory->CreateEncoder(GUID_ContainerFormatPng,nullptr,&encoder),"PNG encoder failed.");preview::Check(encoder->Initialize(stream.Get(),WICBitmapEncoderNoCache),"PNG initialization failed.");preview::Check(encoder->CreateNewFrame(&frame,&options),"PNG frame failed.");preview::Check(frame->Initialize(options.Get()),"PNG frame initialization failed.");preview::Check(frame->SetSize(desc.Width,desc.Height),"PNG dimensions failed.");GUID rgba=GUID_WICPixelFormat32bppBGRA;preview::Check(frame->SetPixelFormat(&rgba),"PNG format failed.");if(rgba!=GUID_WICPixelFormat32bppBGRA)throw std::runtime_error("Encoder changed pixel format.");auto bgra=pixels;for(size_t i=0;i<bgra.size();i+=4)std::swap(bgra[i],bgra[i+2]);preview::Check(frame->WritePixels(desc.Height,desc.Width*4,static_cast<UINT>(bgra.size()),reinterpret_cast<BYTE*>(bgra.data())),"PNG write failed.");preview::Check(frame->Commit(),"PNG frame commit failed.");preview::Check(encoder->Commit(),"PNG commit failed.");
    }
    return resource::HashBytes(pixels);
}
int wmain(int argc,wchar_t** argv) {
    try {
      CoInitializeEx(nullptr,COINIT_MULTITHREADED);
      preview::Scene scene;
      if(argc==3){auto path=std::filesystem::absolute(argv[1]);auto raw=Read(path,16*1024*1024);scene=preview::Decode(ui::Json::parse(raw),[&](const std::string& n,const std::string&,size_t max){return Read(path.parent_path()/n,max);},resource::HashBytes(raw));}
      else {
        // Known skinned geometry exercises animation, camera and state
        // restoration on WARP without requiring proprietary game fixtures.
        scene.id=std::string(64,'a');scene.sim="1";scene.outfit="2";scene.form=1;scene.bones.push_back({"root",1,-1});scene.minimum={-.5f,0,0};scene.maximum={.5f,1,0};
        resource::Pixels texture;texture.width=texture.height=2;texture.rgba={255,80,20,255,20,200,255,255,60,255,120,255,200,20,255,255};scene.surfaces.push_back({texture});
        preview::Mesh mesh;mesh.vertices={{{-.5f,0,0},{0,0,1},{0,1},{0,0,0,0},{1,0,0,0}},{{.5f,0,0},{0,0,1},{1,1},{0,0,0,0},{1,0,0,0}},{{0,1,0},{0,0,1},{.5f,0},{0,0,0,0},{1,0,0,0}}};mesh.indices={0,1,2};scene.meshes.push_back(mesh);
        preview::Clip clip;clip.name="known-translation";clip.duration=1;clip.step=.1f;preview::Curve c;c.hash=1;c.kind=1;c.frames={ {0,{0,0,0,0}},{1,{.3f,0,0,0}} };clip.curves.push_back(c);scene.clips.push_back(clip);
      }
      preview::ComPtr<ID3D11Device> device;preview::ComPtr<ID3D11DeviceContext> context;D3D_FEATURE_LEVEL level;
      preview::Check(D3D11CreateDevice(nullptr,D3D_DRIVER_TYPE_WARP,nullptr,D3D11_CREATE_DEVICE_BGRA_SUPPORT,nullptr,0,D3D11_SDK_VERSION,&device,&level,&context),"WARP device failed.");
      D3D11_VIEWPORT original{7,11,133,177,.2f,.8f};context->RSSetViewports(1,&original);
      preview::ComPtr<ID3D11Buffer> originalBuffer;D3D11_BUFFER_DESC desc{};desc.ByteWidth=64;desc.Usage=D3D11_USAGE_DEFAULT;
      desc.BindFlags=D3D11_BIND_VERTEX_BUFFER|D3D11_BIND_INDEX_BUFFER;
      preview::Check(device->CreateBuffer(&desc,nullptr,&originalBuffer),"Original pipeline buffer failed.");
      preview::ComPtr<ID3D11Buffer> originalConstants;desc.BindFlags=D3D11_BIND_CONSTANT_BUFFER;
      preview::Check(device->CreateBuffer(&desc,nullptr,&originalConstants),"Original constant buffer failed.");
      ID3D11Buffer* originalRaw=originalBuffer.Get();UINT stride=16,offset=4;
      context->IASetVertexBuffers(0,1,&originalRaw,&stride,&offset);context->IASetIndexBuffer(originalRaw,DXGI_FORMAT_R16_UINT,2);
      ID3D11Buffer* constantRaw=originalConstants.Get();context->VSSetConstantBuffers(0,1,&constantRaw);context->PSSetConstantBuffers(0,1,&constantRaw);
      context->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_LINELIST);
      preview::ComPtr<ID3D11Texture2D> originalTexture;preview::ComPtr<ID3D11RenderTargetView> originalTarget;
      D3D11_TEXTURE2D_DESC td{};td.Width=td.Height=32;td.MipLevels=td.ArraySize=1;td.Format=DXGI_FORMAT_R8G8B8A8_UNORM;td.SampleDesc.Count=1;td.BindFlags=D3D11_BIND_RENDER_TARGET;
      preview::Check(device->CreateTexture2D(&td,nullptr,&originalTexture),"Original render target failed.");
      preview::Check(device->CreateRenderTargetView(originalTexture.Get(),nullptr,&originalTarget),"Original RTV failed.");
      ID3D11RenderTargetView* originalRtv=originalTarget.Get();context->OMSetRenderTargets(1,&originalRtv,nullptr);
      preview::Renderer renderer;renderer.Load(device.Get(),std::move(scene));renderer.view.playing=false;
      renderer.Control({{"yaw",0.2},{"playing",false},{"clip",0},{"time",0.0}});
      try{renderer.Control({{"yaw",0.8},{"distance",0.01}});throw std::runtime_error("Out-of-range view accepted.");}
      catch(const std::runtime_error&){if(renderer.view.yaw!=.2f)throw std::runtime_error("Malformed view partially applied.");}
      renderer.view.yaw=0;
      if(!renderer.scene.meshes[0].vertices.empty()||!renderer.scene.surfaces[0].diffuse.rgba.empty())throw std::runtime_error("GPU upload retained duplicate CPU assets.");
      renderer.Render(context.Get(),640,900,0);
      std::filesystem::path output=argc==3?argv[2]:L"";if(!output.empty())std::filesystem::create_directories(output);
      const auto first=Capture(device.Get(),context.Get(),renderer.Target(),output.empty()?std::filesystem::path{}:output/L"front.png");
      D3D11_VIEWPORT after{};UINT count=1;context->RSGetViewports(&count,&after);
      if(count!=1||std::memcmp(&after,&original,sizeof(after)))throw std::runtime_error("Preview leaked viewport state.");
      preview::ComPtr<ID3D11Buffer> restored;UINT restoredStride=0,restoredOffset=0;
      context->IAGetVertexBuffers(0,1,&restored,&restoredStride,&restoredOffset);
      if(restored.Get()!=originalRaw||restoredStride!=stride||restoredOffset!=offset)throw std::runtime_error("Preview leaked vertex bindings.");
      restored.Reset();DXGI_FORMAT format{};context->IAGetIndexBuffer(&restored,&format,&restoredOffset);
      if(restored.Get()!=originalRaw||format!=DXGI_FORMAT_R16_UINT||restoredOffset!=2)throw std::runtime_error("Preview leaked index binding.");
      restored.Reset();context->VSGetConstantBuffers(0,1,&restored);if(restored.Get()!=constantRaw)throw std::runtime_error("Preview leaked VS constants.");
      restored.Reset();context->PSGetConstantBuffers(0,1,&restored);if(restored.Get()!=constantRaw)throw std::runtime_error("Preview leaked PS constants.");
      D3D11_PRIMITIVE_TOPOLOGY topology{};context->IAGetPrimitiveTopology(&topology);if(topology!=D3D11_PRIMITIVE_TOPOLOGY_LINELIST)throw std::runtime_error("Preview leaked topology.");
      preview::ComPtr<ID3D11RenderTargetView> restoredTarget;context->OMGetRenderTargets(1,&restoredTarget,nullptr);
      if(restoredTarget.Get()!=originalRtv)throw std::runtime_error("Preview leaked render targets.");
      renderer.view.time=.5f;renderer.Render(context.Get(),640,900,0);const auto animated=Capture(device.Get(),context.Get(),renderer.Target(),output.empty()?std::filesystem::path{}:output/L"animated.png");
      if(!renderer.scene.clips.empty()&&animated==first)throw std::runtime_error("Animation produced no pixel change.");
      renderer.view.yaw=1.0f;renderer.Render(context.Get(),640,900,0);const auto rotated=Capture(device.Get(),context.Get(),renderer.Target(),output.empty()?std::filesystem::path{}:output/L"rotated.png");
      if(rotated==animated)throw std::runtime_error("Orbit produced no pixel change.");
      renderer.Control({{"projection","orthographic"},{"controls","blender"},{"preset","body"},{"roll",.2}});
      renderer.Render(context.Get(),640,900,0);const auto orthographic=Capture(device.Get(),context.Get(),renderer.Target());
      if(orthographic==rotated||!renderer.view.orthographic||!renderer.view.blenderControls)throw std::runtime_error("Orthographic camera did not change projection.");
      renderer.Control({{"preset","top"}});renderer.Render(context.Get(),640,900,0);
      if(Capture(device.Get(),context.Get(),renderer.Target())==orthographic)throw std::runtime_error("Top camera did not change pixels.");
      const auto before=renderer.view;
      for(const auto& invalid:std::vector<ui::Json>{{{"preset","missing"}},{{"fov",0}},{{"projection","missing"}},{{"controls","missing"}},{{"yaw",.9},{"ortho_scale",0}},{{"preset","selected"},{"focus_body_type",65000}}}){
        bool refused=false;try{renderer.Control(invalid);}catch(const std::runtime_error&){refused=true;}
        if(!refused||renderer.view.yaw!=before.yaw||renderer.view.pitch!=before.pitch||renderer.view.fov!=before.fov||renderer.view.orthographic!=before.orthographic)throw std::runtime_error("Malformed camera control partially applied.");
      }
      renderer.Control({{"preset","selected"},{"focus_body_type",renderer.scene.meshes[0].body},{"controls","simple"}});
      if(renderer.view.blenderControls)throw std::runtime_error("Simple controls were not selected.");
      renderer.Control({{"fov",90},{"preset","reset"}});renderer.Control({{"preset","reset"}});
      if(renderer.view.fov!=35||renderer.view.orthographic||renderer.view.pitch!=0)throw std::runtime_error("Camera reset did not restore framing settings.");
      renderer.Pan(.2f,.1f);if(!std::isfinite(renderer.view.pan)||!std::isfinite(renderer.view.panDepth))throw std::runtime_error("Camera pan is nonfinite.");
      std::cout<<ui::Json({{"ok",true},{"sim_id",renderer.scene.sim},{"form",renderer.scene.form},{"outfit_id",renderer.scene.outfit},{"meshes",renderer.scene.meshes.size()},{"clips",renderer.scene.clips.size()},{"front_sha256",first},{"animated_sha256",animated},{"rotated_sha256",rotated},{"pipeline_restored",true},{"game_contacted",false}}).dump()<<"\n";
      return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
