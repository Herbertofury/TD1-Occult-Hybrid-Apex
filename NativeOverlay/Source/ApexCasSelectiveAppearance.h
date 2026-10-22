// Category-scoped copies operate on detached complete appearance packets.
// Identity, gameplay, other forms and unknown/unselected fields stay owned by
// the destination. No stock controller-wide two-slot synchronization is used.
#pragma once
#include "ApexCasHouseholdWire.h"
#include <array>
#include <algorithm>

namespace td1::nativecas::selective {
namespace w=wire;
constexpr std::uint32_t Supported=2|4|8|16|32|64|128|256|1024|4096|16384|
    32768|65536|131072|262144|524288|1048576|2097152|4194304|8388608|134217728;
inline void Validate(std::uint32_t flags) {
    if(flags&~Supported)throw std::runtime_error("Unsupported pair appearance category.");
}
inline bool Body(std::uint64_t body,std::uint32_t flags) {
    const bool clothes=(flags&256)!=0;
    if(body==1)return clothes || (flags&32768);
    if(body==2 || body==75)return flags&(32|1048576);
    if(body==3 || body==4)return flags&8;
    if(body==5 || body==6)return clothes || (flags&65536);
    if(body==7)return clothes || (flags&131072);
    if(body==8)return clothes || (flags&262144);
    if((body>=9 && body<=27) || body==36 || body==42 || body==73 || body==74 || body==110 || body==115 || body==117)
        return clothes || (flags&16384);
    if(body==28)return flags&(64|2097152);
    if((body>=29 && body<=33) || body==37)return flags&524288;
    if(body==34 || body==35 || body==63)return flags&4194304;
    if((body>=45 && body<=54) || body==113)return flags&1024;
    if((body>=38 && body<=41) || body==43 || body==44 || (body>=55 && body<=58) ||
       body==62 || (body>=64 && body<=72) || body==76 || body==77 ||
       (body>=82 && body<=87) || (body>=89 && body<=100) || body==112 || body==116)return flags&4096;
    if(body>=78 && body<=81)return flags&8388608;
    if(body==114)return flags&134217728;
    return false; // Unknown/future body types are never silently included.
}
inline const w::Field* Optional(const std::vector<w::Field>& rows,unsigned number,unsigned type=2) {
    const w::Field* found=nullptr;
    for(const auto& row:rows)if(row.number==number) {
        if(found || row.type!=type)throw std::runtime_error("Ambiguous appearance field.");found=&row;
    }
    return found;
}
inline std::string SwapFields(const std::string& target,const std::string& source,const std::set<unsigned>& numbers) {
    std::string out;for(const auto& f:w::Fields(target))if(!numbers.count(f.number))out+=f.raw;
    for(const auto& f:w::Fields(source))if(numbers.count(f.number))out+=f.raw;
    return out;
}
inline std::string Morphs(const std::string& target,const std::string& source,std::uint32_t flags) {
    std::set<unsigned> groups;
    if(flags&8)groups.insert({1,2,4}); // Preset sculpts, face and aged-face modifiers.
    if(flags&(2|4))groups.insert({3,5}); // Body and aged-body modifiers.
    return SwapFields(target,source,groups);
}
inline std::string PartList(const std::string& target,const std::string& source,std::uint32_t flags) {
    std::string out;
    for(const auto& f:w::Fields(target)) {
        if(f.number!=1) {out+=f.raw;continue;}
        if(f.type!=2)throw std::runtime_error("Invalid genetic part row.");
        if(!Body(w::Scalar(w::One(w::Fields(f.value),2,0)),flags))out+=f.raw;
    }
    for(const auto& f:w::Fields(source))if(f.number==1) {
        if(f.type!=2)throw std::runtime_error("Invalid source genetic part row.");
        if(Body(w::Scalar(w::One(w::Fields(f.value),2,0)),flags))out+=f.raw;
    }
    return out;
}
inline std::vector<std::uint64_t> Numbers(const std::string& container,bool fixed=false) {
    std::vector<std::uint64_t> out;
    for(const auto& f:w::Fields(container))if(f.number==1) {
        if((!fixed && f.type==0) || (fixed && f.type==1))out.push_back(w::Scalar(f));
        else if(f.type==2 && fixed) {
            if(f.value.size()%8)throw std::runtime_error("Misaligned fixed64 outfit identifiers.");
            for(std::size_t at=0;at<f.value.size();at+=8) {
                std::uint64_t value=0;for(unsigned n=0;n<8;++n)value|=std::uint64_t(static_cast<unsigned char>(f.value[at+n]))<<(8*n);
                out.push_back(value);
            }
        }
        else if(f.type==2) {std::size_t at=0;while(at<f.value.size())out.push_back(w::ReadVar(f.value,at));}
        else throw std::runtime_error("Unsupported outfit parallel array encoding.");
        if(out.size()>4096)throw std::runtime_error("Outfit part limit exceeded.");
    }
    return out;
}
inline std::string WriteNumbers(const std::string& target,const std::vector<std::uint64_t>& values,bool fixed=false) {
    std::string out;for(const auto& f:w::Fields(target))if(f.number!=1)out+=f.raw;
    // The installed schema packs these varint arrays. Preserve container
    // extensions; empty arrays stay empty instead of inventing a zero row.
    std::string packed;for(const auto n:values) {
        if(fixed)for(unsigned i=0;i<8;++i)packed+=char(n>>(8*i));else packed+=w::Var(n);
    }
    if(!packed.empty())out+=w::Bytes(1,packed);
    return out;
}
using Row=std::array<std::uint64_t,5>;
struct OutfitParts {std::vector<Row> rows;std::array<bool,5> present{};std::array<std::string,5> containers;};
inline OutfitParts Parts(const std::string& outfit) {
    const auto fields=w::Fields(outfit);const unsigned keys[]={5,7,12,14,15};
    std::array<std::vector<std::uint64_t>,5> arrays;OutfitParts out;
    for(unsigned i=0;i<5;++i)if(const auto f=Optional(fields,keys[i])) {
        out.containers[i]=f->value;arrays[i]=Numbers(f->value,i==0);out.present[i]=!arrays[i].empty();
    }
    if(arrays[0].size()!=arrays[1].size())throw std::runtime_error("Misaligned part/body arrays.");
    for(unsigned i=2;i<5;++i)if(out.present[i] && arrays[i].size()!=arrays[0].size())
        throw std::runtime_error("Misaligned optional part arrays.");
    for(std::size_t n=0;n<arrays[0].size();++n) {
        Row row{};for(unsigned i=0;i<5;++i)if(out.present[i])row[i]=arrays[i][n];out.rows.push_back(row);
    }
    return out;
}
inline std::string Outfit(const std::string& target,const std::string& source,std::uint32_t flags) {
    const auto a=Parts(target),b=Parts(source);std::vector<Row> rows;
    const bool additions=std::any_of(b.rows.begin(),b.rows.end(),[&](const Row& r){return Body(r[1],flags);});
    const bool retained=std::any_of(a.rows.begin(),a.rows.end(),[&](const Row& r){return !Body(r[1],flags);});
    if(additions && retained)for(unsigned i=2;i<5;++i)if(a.present[i]!=b.present[i])
        throw std::runtime_error("Selected parts need incompatible optional metadata; no copy applied.");
    for(const auto& row:a.rows)if(!Body(row[1],flags))rows.push_back(row);
    for(const auto& row:b.rows)if(Body(row[1],flags))rows.push_back(row);
    std::stable_sort(rows.begin(),rows.end(),[](const Row& x,const Row& y){return x[1]<y[1];});
    if(rows.size()>4096)throw std::runtime_error("Copied outfit exceeds its part bound.");
    const unsigned keys[]={5,7,12,14,15};std::string out;
    for(const auto& f:w::Fields(target))if(std::find(std::begin(keys),std::end(keys),f.number)==std::end(keys))out+=f.raw;
    for(unsigned i=0;i<5;++i) {
        std::vector<std::uint64_t> values;
        const bool present=i<2 || (retained?a.present[i]:additions?b.present[i]:a.present[i]);
        if(present)for(const auto& row:rows)values.push_back(row[i]);
        const auto container=WriteNumbers(a.containers[i],values,i==0);
        if(!container.empty())out+=w::Bytes(keys[i],container);
    }
    return out;
}
inline std::uint64_t OutfitCategory(const std::string& outfit);
inline std::string Outfits(const std::string& target,const std::string& source,std::uint32_t flags) {
    using Key=std::pair<std::uint64_t,unsigned>;std::map<Key,std::string> sources;std::map<std::uint64_t,unsigned> counts;
    for(const auto& f:w::Fields(source))if(f.number==1) {
        if(f.type!=2)throw std::runtime_error("Invalid source outfit.");
        const auto kind=OutfitCategory(f.value);sources.emplace(Key{kind,counts[kind]++},f.value);
    }
    counts.clear();std::string out;
    for(const auto& f:w::Fields(target)) {
        if(f.number!=1) {out+=f.raw;continue;}
        if(f.type!=2)throw std::runtime_error("Invalid destination outfit.");
        const auto kind=OutfitCategory(f.value);const auto at=sources.find({kind,counts[kind]++});
        out+=at==sources.end()?f.raw:w::Bytes(1,Outfit(f.value,at->second,flags));
    }
    return out;
}
inline std::uint64_t OutfitCategory(const std::string& outfit) {
    const auto rows=w::Fields(outfit);const auto f=Optional(rows,2,0);return f?w::Scalar(*f):0;
}
inline OutfitParts Equipped(const std::string& packet,std::uint64_t category,std::uint64_t ordinal) {
    if(category>255 || ordinal>255)throw std::runtime_error("Outfit selection exceeds its bound.");
    const auto root=w::Fields(packet);const auto outfits=Optional(root,21);
    if(!outfits)throw std::runtime_error("The current appearance has no outfit list.");
    std::uint64_t seen=0;
    for(const auto& f:w::Fields(outfits->value))if(f.number==1) {
        if(f.type!=2)throw std::runtime_error("Invalid equipped outfit encoding.");
        if(OutfitCategory(f.value)==category && seen++==ordinal)return Parts(f.value);
    }
    throw std::runtime_error("The exact requested outfit is absent.");
}
struct EquippedOutfit {std::uint64_t id=0,category=0,ordinal=0;OutfitParts parts;};
inline std::vector<EquippedOutfit> EquippedInventory(const std::string& packet) {
    const auto root=w::Fields(packet);const auto list=Optional(root,21);
    if(!list)throw std::runtime_error("Equipped owner has no complete outfit list.");
    std::vector<EquippedOutfit> result;std::map<std::uint64_t,unsigned> ordinals;std::size_t count=0;
    for(const auto& f:w::Fields(list->value))if(f.number==1) {
        if(f.type!=2 || result.size()>=128)throw std::runtime_error("Equipped outfit inventory exceeds its bound.");
        const auto fields=w::Fields(f.value);const auto identity=Optional(fields,1,0);
        const auto id=identity?w::Scalar(*identity):0;
        const auto category=OutfitCategory(f.value);
        if(category>255)throw std::runtime_error("Equipped outfit identity differs.");
        auto parts=Parts(f.value);
        for(const auto& part:parts.rows)if(!part[0] || part[1]>0xffffffff || part[4]>0xffffffff || ++count>16384)
            throw std::runtime_error("Equipped part identity exceeds its bound.");
        result.push_back({id,category,ordinals[category]++,std::move(parts)});
    }
    return result;
}
inline std::string Merge(const std::string& target,const std::string& source,std::uint32_t flags) {
    Validate(flags);const auto a=w::Fields(target),b=w::Fields(source);
    if(w::Scalar(w::One(a,1,1))!=w::Scalar(w::One(b,1,1)))throw std::runtime_error("Pair copy crossed Sim identity.");
    std::set<unsigned> scalars;
    if(flags&(2|4))scalars.insert(12);
    if(flags&16)scalars.insert({10,67});
    if(flags&128)scalars.insert({9,11,54});
    if(flags&1024)scalars.insert(75);
    auto result=SwapFields(target,source,scalars);
    for(const unsigned number:{18u,21u,28u}) {
        const bool morph=(flags&(2|4|8))!=0;
        const bool parts=(flags&(Supported&~std::uint32_t(2|4|16|128)))!=0;
        if((number==18 && !morph) || (number==21 && !parts) || (number==28 && !(morph || parts || (flags&128))))continue;
        const auto x=Optional(a,number),y=Optional(b,number);
        if(!x || !y)throw std::runtime_error("Complete scoped appearance requires morph, outfit and genetic data.");
        std::string changed;
        if(number==18)changed=Morphs(x->value,y->value,flags);
        if(number==21)changed=Outfits(x->value,y->value,flags);
        if(number==28) {
            changed=x->value;const auto gx=w::Fields(x->value),gy=w::Fields(y->value);
            std::set<unsigned> names;if(flags&(2|4))names.insert(2);if(flags&128)names.insert({3,4});
            changed=SwapFields(changed,y->value,names);
            for(unsigned n:{1u,5u,6u}) {
                if((n==1 && !morph) || (n!=1 && !parts))continue;
                const auto u=Optional(gx,n),v=Optional(gy,n);
                if(!u && !v)continue;
                if(!u || !v)throw std::runtime_error("Genetic scope is incomplete on this pair.");
                const auto merged=n==1?Morphs(u->value,v->value,flags):PartList(u->value,v->value,flags);
                changed=SwapFields(changed,w::Bytes(n,merged),{n});
            }
        }
        result=SwapFields(result,w::Bytes(number,changed),{number});
    }
    return result;
}
inline std::string MirrorRecord(const std::string& packet,std::uint32_t kind) {
    const auto root=w::Fields(packet);const auto attrs=w::One(root,30,2).value;
    const auto tracker=w::One(w::Fields(attrs),17,2).value;std::string changed;unsigned found=0;
    for(const auto& f:w::Fields(tracker)) {
        if(f.number==3 && f.type==2 && w::Scalar(w::One(w::Fields(f.value),1,0))==kind) {
            ++found;changed+=w::Bytes(3,w::Replace(f.value,packet,w::OccultFields()));
        } else changed+=f.raw;
    }
    if(found!=1)throw std::runtime_error("Scoped copy has no unique destination appearance record.");
    return SwapFields(packet,w::Bytes(30,SwapFields(attrs,w::Bytes(17,changed),{17})),{30});
}
enum class Schema {Root,Outfits,Outfit,Genetics,Parts,Part,Array,Morph,Opaque};
inline std::string Canonical(const std::string& raw,Schema schema) {
    if(schema==Schema::Opaque)return raw;
    auto fields=w::Fields(raw);
    std::stable_sort(fields.begin(),fields.end(),[](const w::Field& x,const w::Field& y){return x.number<y.number;});
    std::string out;
    for(const auto& f:fields) {
        Schema child=Schema::Opaque;
        if(schema==Schema::Root) {
            bool appearance=false;for(const auto& p:w::RootFields())if(p.first==f.number)appearance=true;
            if(!appearance)continue;
            if(f.number==21)child=Schema::Outfits;
            if(f.number==28)child=Schema::Genetics;
            if(f.number==18)child=Schema::Morph;
        }
        if(schema==Schema::Outfits && f.number==1)child=Schema::Outfit;
        if(schema==Schema::Outfit && (f.number==5 || f.number==7 || f.number==12 || f.number==14 || f.number==15))child=Schema::Array;
        if(schema==Schema::Genetics && (f.number==5 || f.number==6))child=Schema::Parts;
        if(schema==Schema::Genetics && f.number==1)child=Schema::Morph;
        if(schema==Schema::Parts && f.number==1)child=Schema::Part;
        out+=f.type==2?w::Bytes(f.number,Canonical(f.value,child)):f.raw;
    }
    return out;
}
inline bool Equivalent(const std::string& expected,const std::string& actual) {
    return Canonical(expected,Schema::Root)==Canonical(actual,Schema::Root);
}
} // namespace td1::nativecas::selective
