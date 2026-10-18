// Read-only Windows Graphics Capture for one exact EA window. No input/focus.
#include <windows.h>
#include <dwmapi.h>
#include <d3d11.h>
#include <dxgi.h>
#include <windows.graphics.capture.interop.h>
#include <windows.graphics.directx.direct3d11.interop.h>
#include <winrt/Windows.Foundation.h>
#include <winrt/Windows.Graphics.Capture.h>
#include <winrt/Windows.Graphics.DirectX.h>
#include <winrt/Windows.Graphics.DirectX.Direct3D11.h>
#include <algorithm>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>
using namespace winrt;
using namespace winrt::Windows::Graphics::Capture;
using namespace winrt::Windows::Graphics::DirectX;
using namespace winrt::Windows::Graphics::DirectX::Direct3D11;

static void Validate(HWND window,DWORD pid,int width,int height) {
    DWORD actual=0;GetWindowThreadProcessId(window,&actual);
    wchar_t title[256]{},type[256]{};GetWindowTextW(window,title,256);GetClassNameW(window,type,256);
    RECT client{};
    if(actual!=pid||!IsWindowVisible(window)||IsIconic(window)||std::wstring(title)!=L"EA"||
       std::wstring(type).rfind(L"Qt",0)!=0||!GetClientRect(window,&client)||client.right!=width||client.bottom!=height)
        throw std::runtime_error("Exact visible EA window identity changed.");
    HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,pid);
    if(!process)throw std::runtime_error("EA process image cannot be verified.");
    wchar_t image[32768]{};DWORD length=32768;const bool queried=QueryFullProcessImageNameW(process,0,image,&length)!=0;CloseHandle(process);
    const std::wstring path(image,length);const auto separator=path.find_last_of(L"\\/");
    if(!queried||separator==std::wstring::npos||path.substr(separator+1)!=L"EADesktop.exe")
        throw std::runtime_error("Capture target is not the installed EA process.");
}

int wmain(int argc,wchar_t** argv) {
    try {
        if(argc!=6)throw std::runtime_error("Expected HWND, PID, client width, client height and new BMP output.");
        const auto window=reinterpret_cast<HWND>(std::stoull(argv[1]));
        const auto pid=static_cast<DWORD>(std::stoul(argv[2]));const int width=std::stoi(argv[3]),height=std::stoi(argv[4]);
        if(!pid||width<200||height<150||width>2600||height>2600)throw std::runtime_error("EA viewport bound exceeded.");
        Validate(window,pid,width,height);init_apartment(apartment_type::multi_threaded);
        if(!GraphicsCaptureSession::IsSupported())throw std::runtime_error("Windows Graphics Capture is unavailable.");
        com_ptr<ID3D11Device> device;com_ptr<ID3D11DeviceContext> context;
        check_hresult(D3D11CreateDevice(nullptr,D3D_DRIVER_TYPE_HARDWARE,nullptr,D3D11_CREATE_DEVICE_BGRA_SUPPORT,
            nullptr,0,D3D11_SDK_VERSION,device.put(),nullptr,context.put()));
        com_ptr<::IInspectable> inspectable;
        check_hresult(CreateDirect3D11DeviceFromDXGIDevice(device.as<IDXGIDevice>().get(),inspectable.put()));
        auto captureDevice=inspectable.as<IDirect3DDevice>();
        auto interop=get_activation_factory<GraphicsCaptureItem,IGraphicsCaptureItemInterop>();
        GraphicsCaptureItem item{nullptr};
        check_hresult(interop->CreateForWindow(window,guid_of<GraphicsCaptureItem>(),put_abi(item)));
        const auto size=item.Size();
        if(size.Width<width||size.Height<height||size.Width>2700||size.Height>2700)
            throw std::runtime_error("EA capture dimensions are incompatible with its client.");
        auto pool=Direct3D11CaptureFramePool::CreateFreeThreaded(captureDevice,DirectXPixelFormat::B8G8R8A8UIntNormalized,2,size);
        auto session=pool.CreateCaptureSession(item);session.IsCursorCaptureEnabled(false);session.StartCapture();
        Direct3D11CaptureFrame frame{nullptr};const auto deadline=GetTickCount64()+5000;
        std::vector<unsigned char> pixels;bool captured=false;
        // Qt's first compositor frame can be entirely transparent before its
        // actual dialog surface arrives. Observe later frames within the same
        // fixed lease; a blank frame can never authorize input.
        while(GetTickCount64()<deadline&&!captured) {
        frame=pool.TryGetNextFrame();if(!frame){Sleep(20);continue;}
        if(frame.ContentSize().Width!=size.Width||frame.ContentSize().Height!=size.Height)
            throw std::runtime_error("EA capture resized before readback.");
        RECT bounds{},extended{};POINT origin{0,0};
        if(!GetWindowRect(window,&bounds)||!ClientToScreen(window,&origin))throw std::runtime_error("EA client origin is unavailable.");
        const bool hasExtended=SUCCEEDED(DwmGetWindowAttribute(window,DWMWA_EXTENDED_FRAME_BOUNDS,&extended,sizeof(extended)));
        const auto matches=[&](const RECT& r){return r.right-r.left==size.Width&&r.bottom-r.top==size.Height;};
        RECT chosen{};
        if(matches(bounds))chosen=bounds;
        else if(hasExtended&&matches(extended))chosen=extended;
        else throw std::runtime_error("EA frame-to-client crop cannot be measured exactly.");
        const int left=origin.x-chosen.left,top=origin.y-chosen.top;
        if(left<0||top<0||left+width>size.Width||top+height>size.Height)throw std::runtime_error("EA client crop exceeds captured pixels.");
        auto access=frame.Surface().as<::Windows::Graphics::DirectX::Direct3D11::IDirect3DDxgiInterfaceAccess>();com_ptr<ID3D11Texture2D> source;
        check_hresult(access->GetInterface(__uuidof(ID3D11Texture2D),source.put_void()));
        D3D11_TEXTURE2D_DESC desc{};source->GetDesc(&desc);
        if(desc.Format!=DXGI_FORMAT_B8G8R8A8_UNORM||desc.Width<static_cast<UINT>(size.Width)||desc.Height<static_cast<UINT>(size.Height))
            throw std::runtime_error("EA capture texture format differs.");
        desc.Width=width;desc.Height=height;desc.BindFlags=0;desc.MiscFlags=0;desc.Usage=D3D11_USAGE_STAGING;desc.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
        com_ptr<ID3D11Texture2D> staging;check_hresult(device->CreateTexture2D(&desc,nullptr,staging.put()));
        D3D11_BOX crop{static_cast<UINT>(left),static_cast<UINT>(top),0,static_cast<UINT>(left+width),static_cast<UINT>(top+height),1};
        context->CopySubresourceRegion(staging.get(),0,0,0,0,source.get(),0,&crop);
        D3D11_MAPPED_SUBRESOURCE mapped{};check_hresult(context->Map(staging.get(),0,D3D11_MAP_READ,0,&mapped));
        pixels.resize(static_cast<size_t>(width)*height*4);
        for(int y=0;y<height;++y)std::memcpy(pixels.data()+static_cast<size_t>(y)*width*4,
            static_cast<const unsigned char*>(mapped.pData)+static_cast<size_t>(y)*mapped.RowPitch,static_cast<size_t>(width)*4);
        context->Unmap(staging.get(),0);Validate(window,pid,width,height);
        for(size_t i=4;i<pixels.size();i+=4) {
            if(pixels[i]!=pixels[0]||pixels[i+1]!=pixels[1]||pixels[i+2]!=pixels[2]) {
                captured=true;break;
            }
        }
        if(!captured){frame.Close();frame=nullptr;Sleep(20);}
        }
        if(!captured)throw std::runtime_error("EA window did not produce nonblank client pixels within five seconds.");
        BITMAPFILEHEADER header{};BITMAPINFOHEADER info{};header.bfType=0x4D42;header.bfOffBits=sizeof(header)+sizeof(info);
        header.bfSize=header.bfOffBits+static_cast<DWORD>(pixels.size());info.biSize=sizeof(info);info.biWidth=width;info.biHeight=-height;
        info.biPlanes=1;info.biBitCount=32;info.biSizeImage=static_cast<DWORD>(pixels.size());
        HANDLE output=CreateFileW(argv[5],GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
        if(output==INVALID_HANDLE_VALUE)throw std::runtime_error("Use a new writable EA capture output.");
        DWORD written=0;bool ok=WriteFile(output,&header,sizeof(header),&written,nullptr)&&written==sizeof(header);
        ok=ok&&WriteFile(output,&info,sizeof(info),&written,nullptr)&&written==sizeof(info);
        ok=ok&&WriteFile(output,pixels.data(),static_cast<DWORD>(pixels.size()),&written,nullptr)&&written==pixels.size();CloseHandle(output);
        frame.Close();session.Close();pool.Close();
        if(!ok)throw std::runtime_error("EA capture output was incomplete.");
        std::cout<<"{\"ok\":true,\"foreground_changed\":false,\"input_sent\":false,\"client_width\":"<<width<<",\"client_height\":"<<height<<"}\n";
        return 0;
    } catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
      catch(const winrt::hresult_error& e){std::cerr<<winrt::to_string(e.message())<<'\n';return 1;}
}
