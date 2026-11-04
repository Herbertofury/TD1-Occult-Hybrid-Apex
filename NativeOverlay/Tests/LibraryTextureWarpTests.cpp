#include "ApexLibraryTextureLifetime.h"
#include <d3d11.h>
#include <wrl/client.h>
#include "imgui.h"
#include <cassert>
#include <cstring>
#include <iostream>
#include <map>
#include <string>

using Microsoft::WRL::ComPtr;
using td1::library_texture::Install;

int main() {
    ComPtr<ID3D11Device> device;
    ComPtr<ID3D11DeviceContext> context;
    D3D_FEATURE_LEVEL level{};
    HRESULT hr=D3D11CreateDevice(nullptr,D3D_DRIVER_TYPE_WARP,nullptr,0,nullptr,0,
                                 D3D11_SDK_VERSION,&device,&level,&context);
    if (FAILED(hr)) { std::cerr << "WARP device unavailable, HRESULT=" << std::hex << hr << '\n'; return 2; }
    D3D11_TEXTURE2D_DESC desc{};
    desc.Width=2; desc.Height=1; desc.MipLevels=desc.ArraySize=desc.SampleDesc.Count=1;
    desc.Format=DXGI_FORMAT_R8G8B8A8_UNORM; desc.Usage=D3D11_USAGE_IMMUTABLE;
    desc.BindFlags=D3D11_BIND_SHADER_RESOURCE;
    auto makeView = [&](const unsigned char* bytes) {
        D3D11_SUBRESOURCE_DATA data{}; data.pSysMem=bytes; data.SysMemPitch=8;
        ComPtr<ID3D11Texture2D> texture;
        ComPtr<ID3D11ShaderResourceView> view;
        assert(SUCCEEDED(device->CreateTexture2D(&desc,&data,&texture)) && texture);
        assert(SUCCEEDED(device->CreateShaderResourceView(texture.Get(),nullptr,&view)) && view);
        return view;
    };
    const unsigned char a[8]={1,2,3,4,5,6,7,8}, b[8]={8,7,6,5,4,3,2,1};
    std::map<std::string,ID3D11ShaderResourceView*> textures;
    std::map<std::string,ImVec2> sizes;
    auto first=makeView(a);
    assert(Install(textures,sizes,std::string("same"),first,ImVec2(2,1),1));
    ComPtr<ID3D11ShaderResourceView> oldReference=textures.at("same");
    auto next=makeView(b);
    assert(Install(textures,sizes,std::string("same"),next,ImVec2(2,1),1));
    assert(!first && !next && textures.size()==1 && textures.at("same")!=oldReference.Get());
    auto blocked=makeView(a);
    assert(!Install(textures,sizes,std::string("other"),blocked,ImVec2(2,1),1));
    assert(blocked && textures.size()==1 && !textures.count("other"));
    ComPtr<ID3D11Resource> held;
    textures.at("same")->GetResource(&held);
    auto stagingDesc=desc;
    stagingDesc.Usage=D3D11_USAGE_STAGING; stagingDesc.BindFlags=0; stagingDesc.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
    ComPtr<ID3D11Texture2D> staging;
    assert(SUCCEEDED(device->CreateTexture2D(&stagingDesc,nullptr,&staging)) && staging);
    context->CopyResource(staging.Get(),held.Get());
    D3D11_MAPPED_SUBRESOURCE mapped{};
    assert(SUCCEEDED(context->Map(staging.Get(),0,D3D11_MAP_READ,0,&mapped)));
    assert(std::memcmp(mapped.pData,b,sizeof(b))==0);
    context->Unmap(staging.Get(),0);
    textures.at("same")->Release();
    std::cout << "PASS: real D3D11 WARP views, full-capacity replacement and pixel readback\n";
}
