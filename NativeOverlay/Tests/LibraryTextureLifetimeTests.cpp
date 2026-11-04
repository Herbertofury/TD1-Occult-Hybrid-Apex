#include "ApexLibraryTextureLifetime.h"
#include <cassert>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>
#include <unknwn.h>
#include <wrl/client.h>
#include "imgui.h"

struct View {
    int releases = 0;
    void Release() { ++releases; }
};
struct Holder {
    View* ptr;
    explicit Holder(View* p) : ptr(p) {}
    ~Holder() { if (ptr) ptr->Release(); }
    View* Get() const { return ptr; }
    View* Detach() { View* result=ptr; ptr=nullptr; return result; }
};
struct Size { float x, y; };
template<class V> struct FailingMap : std::map<std::string,V> {
    using Base=std::map<std::string,V>;
    bool fail = false;
    template<class K,class T>
    auto emplace(K&& key,T&& value) -> decltype(std::declval<Base&>().emplace(std::forward<K>(key),std::forward<T>(value))) {
        if (fail) throw std::bad_alloc();
        return Base::emplace(std::forward<K>(key),std::forward<T>(value));
    }
};
using td1::library_texture::Install;

void replacement_at_limit_and_release() {
    std::map<std::string,View*> textures;
    std::map<std::string,Size> sizes;
    View original[60], replacement, refused;
    for(int i=0;i<60;++i) {
        const auto key=std::to_string(i); Holder h(&original[i]);
        assert(Install(textures,sizes,key,h,Size{1,2},60));
        assert(!h.Get());
    }
    {
        Holder h(&replacement);
        assert(Install(textures,sizes,std::string("0"),h,Size{3,4},60));
        assert(!h.Get() && original[0].releases==1);
        assert(textures.at("0")==&replacement && sizes.at("0").x==3);
        assert(textures.size()==60 && sizes.size()==60);
    }
    {
        Holder h(&refused);
        assert(!Install(textures,sizes,std::string("61"),h,Size{1,1},60));
        assert(h.Get()==&refused && textures.size()==60);
    }
    assert(refused.releases==1);
    for(auto& entry:textures)entry.second->Release();
    assert(replacement.releases==1);
    for(auto& view:original)assert(view.releases==1);
}

void failure_preserves_existing_and_rolls_back_new() {
    FailingMap<View*> textures;
    FailingMap<Size> sizes;
    View old, newer;
    textures.emplace(std::string("old"),&old);
    sizes.emplace(std::string("old"),Size{1,2});
    sizes.fail=true;
    {
        Holder h(&newer);
        bool threw=false;
        try { Install(textures,sizes,std::string("new"),h,Size{3,4},60); }
        catch(const std::bad_alloc&) { threw=true; }
        assert(threw && h.Get()==&newer);
        assert(textures.size()==1 && sizes.size()==1 && textures.at("old")==&old);
        assert(old.releases==0 && sizes.at("old").x==1);
    }
    assert(newer.releases==1);
    View next;
    sizes.erase("old");
    {
        Holder h(&next);
        bool threw=false;
        try { Install(textures,sizes,std::string("old"),h,Size{3,4},60); }
        catch(const std::bad_alloc&) { threw=true; }
        assert(threw && textures.at("old")==&old && old.releases==0);
    }
    assert(next.releases==1);
    View rejected;
    sizes.fail=false;
    sizes.emplace(std::string("stale"),Size{9,9});
    {
        Holder h(&rejected);
        assert(!Install(textures,sizes,std::string("stale"),h,Size{2,2},60));
        assert(!textures.count("stale") && sizes.at("stale").x==9);
    }
    assert(rejected.releases==1);
    View allocationFail;
    textures.fail=true;
    {
        Holder h(&allocationFail);
        bool threw=false;
        try { Install(textures,sizes,std::string("missing"),h,Size{3,4},60); }
        catch(const std::bad_alloc&) { threw=true; }
        assert(threw && textures.at("old")==&old && !textures.count("missing"));
    }
    assert(allocationFail.releases==1 && old.releases==0);
    old.Release();
}

void repeated_replacement_and_empty_holder() {
    std::map<std::string,View*> textures;
    std::map<std::string,Size> sizes;
    std::vector<View> views(101);
    for(int i=0;i<=100;++i) {
        Holder h(&views[i]);
        assert(Install(textures,sizes,std::string("same"),h,Size{float(i),1},60));
    }
    for(int i=0;i<100;++i)assert(views[i].releases==1);
    assert(views[100].releases==0 && textures.size()==1 && sizes.at("same").x==100);
    Holder empty(nullptr);
    assert(!Install(textures,sizes,std::string("same"),empty,Size{3,3},60));
    assert(textures.at("same")==&views[100]);
    textures.at("same")->Release();
    assert(views[100].releases==1);
}

struct ComView : IUnknown {
    ULONG references=1, releases=0;
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID, void** result) override {
        *result=nullptr;
        return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return ++references; }
    ULONG STDMETHODCALLTYPE Release() override { ++releases; return --references; }
};

void real_wrl_holder_and_imgui_dimensions() {
    std::map<std::string,IUnknown*> textures;
    std::map<std::string,ImVec2> sizes;
    ComView old, next;
    Microsoft::WRL::ComPtr<IUnknown> first, second;
    first.Attach(&old); second.Attach(&next);
    assert(Install(textures,sizes,std::string("actual-types"),first,ImVec2(16,32),60));
    assert(Install(textures,sizes,std::string("actual-types"),second,ImVec2(64,128),60));
    assert(!first && !second && old.references==0 && old.releases==1);
    assert(textures.at("actual-types")==&next && sizes.at("actual-types").x==64);
    textures.at("actual-types")->Release();
    assert(next.references==0 && next.releases==1);
}

int main() {
    replacement_at_limit_and_release();
    failure_preserves_existing_and_rolls_back_new();
    repeated_replacement_and_empty_holder();
    real_wrl_holder_and_imgui_dimensions();
    std::cout << "PASS: ownership, repeated replacement, capacity, rollback, null holder\n";
}
