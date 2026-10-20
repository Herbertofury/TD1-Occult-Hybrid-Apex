// Exact-build CAS export projection. Keep unrelated fields and unknown wire
// data intact; replace appearance fields only from their independent owners.
#pragma once
#include <cstdint>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace td1::nativecas::wire {
constexpr std::size_t Limit=8*1024*1024;
struct Field {std::uint32_t number;unsigned type;std::string raw,value;};
inline std::uint64_t ReadVar(const std::string& raw,std::size_t& at) {
    std::uint64_t n=0;
    for(unsigned shift=0;shift<70;shift+=7) {
        if(at>=raw.size())throw std::runtime_error("Truncated native protobuf varint.");
        const auto c=static_cast<unsigned char>(raw[at++]);
        if(shift==63 && c>1)throw std::runtime_error("Native protobuf varint overflow.");
        n|=std::uint64_t(c&127)<<shift;
        if(!(c&128))return n;
    }
    throw std::runtime_error("Unbounded native protobuf varint.");
}
inline std::string Var(std::uint64_t n) {
    std::string out;
    while(n>127) {out+=char((n&127)|128);n>>=7;}
    out+=char(n);return out;
}
inline void Skip(const std::string& raw,std::size_t& at,unsigned type,std::uint32_t number,unsigned depth) {
    if(depth>32)throw std::runtime_error("Native protobuf group depth exceeds its bound.");
    if(type==0) {ReadVar(raw,at);return;}
    if(type==3) {
        while(at<raw.size()) {
            const auto key=ReadVar(raw,at);const auto child=key>>3;const auto kind=unsigned(key&7);
            if(!child || child>536870911)throw std::runtime_error("Invalid native protobuf group field.");
            if(kind==4) {
                if(child!=number)throw std::runtime_error("Mismatched native protobuf group end.");
                return;
            }
            Skip(raw,at,kind,static_cast<std::uint32_t>(child),depth+1);
        }
        throw std::runtime_error("Unterminated native protobuf group.");
    }
    std::uint64_t size=type==1?8:type==5?4:0;
    if(type==2)size=ReadVar(raw,at);
    else if(type!=1 && type!=5)throw std::runtime_error("Invalid native protobuf wire type.");
    if(size>raw.size()-at)throw std::runtime_error("Truncated native protobuf field.");
    at+=static_cast<std::size_t>(size);
}
inline std::vector<Field> Fields(const std::string& raw) {
    if(raw.size()>Limit)throw std::runtime_error("Native protobuf exceeds its complete export bound.");
    std::vector<Field> out;std::size_t at=0;
    while(at<raw.size()) {
        const auto begin=at;const auto key=ReadVar(raw,at);const auto number=key>>3;const auto type=unsigned(key&7);
        if(!number || number>536870911 || type==4)throw std::runtime_error("Invalid native protobuf field key.");
        auto payload=at;
        if(type==2) {const auto size=ReadVar(raw,at);payload=at;
            if(size>raw.size()-at)throw std::runtime_error("Truncated native protobuf bytes.");at+=static_cast<std::size_t>(size);}
        else Skip(raw,at,type,static_cast<std::uint32_t>(number),0);
        out.push_back({static_cast<std::uint32_t>(number),type,raw.substr(begin,at-begin),raw.substr(payload,at-payload)});
        if(out.size()>65536)throw std::runtime_error("Native protobuf field count exceeds its bound.");
    }
    return out;
}
inline std::string Retag(const Field& f,std::uint32_t number) {
    if(f.type==3)throw std::runtime_error("Appearance schema unexpectedly contains a protobuf group.");
    return Var((std::uint64_t(number)<<3)|f.type)+(f.type==2?Var(f.value.size()):std::string())+f.value;
}
inline std::string Bytes(std::uint32_t number,const std::string& value) {
    return Var((std::uint64_t(number)<<3)|2)+Var(value.size())+value;
}
inline const Field& One(const std::vector<Field>& fields,std::uint32_t number,unsigned type) {
    const Field* found=nullptr;
    for(const auto& f:fields)if(f.number==number) {
        if(found || f.type!=type)throw std::runtime_error("Duplicate or incorrectly typed native schema field.");found=&f;
    }
    if(!found)throw std::runtime_error("Required native schema field is absent.");
    return *found;
}
inline std::uint64_t Scalar(const Field& f) {
    if(f.type==0) {std::size_t at=0;const auto value=ReadVar(f.value,at);
        if(at!=f.value.size())throw std::runtime_error("Native scalar has trailing bytes.");return value;}
    if(f.type==1 && f.value.size()==8) {std::uint64_t value=0;
        for(unsigned n=0;n<8;++n)value|=std::uint64_t(static_cast<unsigned char>(f.value[n]))<<(n*8);return value;}
    throw std::runtime_error("Native scalar has an unexpected wire type.");
}
inline std::string Replace(const std::string& original,const std::string& source,
                           const std::vector<std::pair<std::uint32_t,std::uint32_t>>& mapping) {
    const auto src=Fields(source);std::set<std::uint32_t> targets;std::string result;
    for(const auto& pair:mapping)if(!targets.insert(pair.second).second)throw std::runtime_error("Duplicate appearance destination field.");
    for(const auto& f:Fields(original))if(!targets.count(f.number))result+=f.raw;
    for(const auto& pair:mapping) {
        unsigned count=0;
        for(const auto& f:src)if(f.number==pair.first) {
            if(++count>1 && pair.first!=75 && pair.first!=76)throw std::runtime_error("Duplicate singular native appearance field.");
            result+=Retag(f,pair.second);
        }
    }
    Fields(result);return result;
}
// FileSerialization.SimData -> PersistableOccultTracker.OccultSimData for the
// pinned 1.128.90 build. These are schema field numbers, never memory offsets.
inline const std::vector<std::pair<std::uint32_t,std::uint32_t>>& OccultFields() {
    static const std::vector<std::pair<std::uint32_t,std::uint32_t>> value={
        {12,11},{18,12},{9,13},{11,14},{54,15},{10,16},{28,17},{21,21},{67,22},{75,23}};
    return value;
}
inline const std::vector<std::pair<std::uint32_t,std::uint32_t>>& RootFields() {
    static const std::vector<std::pair<std::uint32_t,std::uint32_t>> value={
        {9,9},{10,10},{11,11},{12,12},{18,18},{21,21},{28,28},{54,54},
        {62,62},{63,63},{67,67},{75,75}};
    return value;
}
inline std::string Household(const std::string& packet,std::uint64_t sim,std::uint32_t mask,
                             const std::map<std::uint32_t,std::string>& owners,const std::string* unselectedActive=nullptr) {
    if(!sim || !(mask&1) || (mask&~127u))throw std::runtime_error("Invalid native household export scope.");
    const auto root=Fields(packet);
    if(Scalar(One(root,1,1))!=sim)throw std::runtime_error("Native household export has another Sim identity.");
    const auto attrs=Fields(One(root,30,2).value);const auto tracker=Fields(One(attrs,17,2).value);
    if((Scalar(One(tracker,1,0))|1)!=mask)throw std::runtime_error("Native household export narrowed or changed occult membership.");
    std::set<std::uint32_t> expected,seen;
    for(std::uint32_t kind=1;kind<=64;kind<<=1)if(mask&kind)expected.insert(kind);
    if(owners.size()!=expected.size())throw std::runtime_error("Native household export lacks complete independent owners.");
    for(const auto& owner:owners)if(!expected.count(owner.first) || Scalar(One(Fields(owner.second),1,1))!=sim)
        throw std::runtime_error("Native household export owner is foreign or has another genus.");
    std::string changedTracker;
    for(const auto& f:tracker) {
        if(f.number!=3) {changedTracker+=f.raw;continue;}
        if(f.type!=2)throw std::runtime_error("Native occult records have an unexpected wire type.");
        const auto record=Fields(f.value);const auto kind=Scalar(One(record,1,0));
        if(kind>64 || !expected.count(static_cast<std::uint32_t>(kind)) || !seen.insert(static_cast<std::uint32_t>(kind)).second)
            throw std::runtime_error("Native occult record roster is missing, duplicated or foreign.");
        changedTracker+=Bytes(3,Replace(f.value,owners.at(static_cast<std::uint32_t>(kind)),OccultFields()));
    }
    if(seen!=expected)throw std::runtime_error("Native household export lost an occult form.");
    std::string changedAttrs;
    for(const auto& f:attrs)changedAttrs+=f.number==17?Bytes(17,changedTracker):f.raw;
    std::string result;
    for(const auto& f:root)result+=f.number==30?Bytes(30,changedAttrs):f.raw;
    if(unselectedActive) {
        if(Scalar(One(Fields(*unselectedActive),1,1))!=sim)throw std::runtime_error("Unselected active owner belongs to another Sim.");
        result=Replace(result,*unselectedActive,RootFields());
    }
    Fields(result);return result;
}
inline std::multiset<std::string> Bag(const std::vector<Field>& fields,std::uint32_t exclude=0) {
    std::multiset<std::string> out;for(const auto& f:fields)if(f.number!=exclude)out.insert(f.raw);return out;
}
inline std::map<std::uint64_t,std::multiset<std::string>> RecordBags(const std::vector<Field>& tracker) {
    std::map<std::uint64_t,std::multiset<std::string>> out;
    for(const auto& f:tracker)if(f.number==3) {
        if(f.type!=2)throw std::runtime_error("Occult output record changed wire type.");
        const auto fields=Fields(f.value);const auto kind=Scalar(One(fields,1,0));
        if(!out.emplace(kind,Bag(fields)).second)throw std::runtime_error("Occult output has duplicate owners.");
    }
    return out;
}
inline bool Equivalent(const std::string& expected,const std::string& actual) {
    // Protobuf serialization may reorder fields. Compare every complete field
    // within the three rewritten containers, including unknown bytes/groups.
    const auto a=Fields(expected),b=Fields(actual);
    if(Bag(a,30)!=Bag(b,30))return false;
    const auto aa=Fields(One(a,30,2).value),ba=Fields(One(b,30,2).value);
    if(Bag(aa,17)!=Bag(ba,17))return false;
    const auto at=Fields(One(aa,17,2).value),bt=Fields(One(ba,17,2).value);
    return Bag(at,3)==Bag(bt,3) && RecordBags(at)==RecordBags(bt);
}
struct Difference {std::string path,expected,actual;};
inline void FieldDifferences(const std::vector<Field>& a,const std::vector<Field>& b,
                             const std::string& path,unsigned exclude,std::vector<Difference>& out) {
    std::map<unsigned,std::multiset<std::string>> left,right;
    for(const auto& f:a)if(f.number!=exclude)left[f.number].insert(f.raw);
    for(const auto& f:b)if(f.number!=exclude)right[f.number].insert(f.raw);
    std::set<unsigned> numbers;for(const auto& f:left)numbers.insert(f.first);for(const auto& f:right)numbers.insert(f.first);
    for(auto n:numbers)if(left[n]!=right[n]) {
        if(out.size()>=128)throw std::runtime_error("Native root difference count exceeds its diagnostic bound.");
        std::string x,y;for(const auto& f:left[n])x+=f;for(const auto& f:right[n])y+=f;
        out.push_back({path+"/"+std::to_string(n),std::move(x),std::move(y)});
    }
}
inline std::vector<Difference> Differences(const std::string& expected,const std::string& actual) {
    std::vector<Difference> out;const auto a=Fields(expected),b=Fields(actual);
    FieldDifferences(a,b,"root",30,out);
    const auto aa=Fields(One(a,30,2).value),ba=Fields(One(b,30,2).value);
    FieldDifferences(aa,ba,"attributes",17,out);
    const auto at=Fields(One(aa,17,2).value),bt=Fields(One(ba,17,2).value);
    FieldDifferences(at,bt,"tracker",3,out);
    const auto records=[](const std::vector<Field>& fields) {
        std::map<std::uint64_t,std::string> result;
        for(const auto& f:fields)if(f.number==3) {
            if(f.type!=2)throw std::runtime_error("Diagnostic occult record changed wire type.");
            const auto kind=Scalar(One(Fields(f.value),1,0));
            if(!result.emplace(kind,f.value).second)throw std::runtime_error("Diagnostic occult record identity is duplicated.");
        }
        return result;
    };
    auto ar=records(at),br=records(bt);std::set<std::uint64_t> kinds;
    for(const auto& f:ar)kinds.insert(f.first);for(const auto& f:br)kinds.insert(f.first);
    for(auto kind:kinds)FieldDifferences(Fields(ar[kind]),Fields(br[kind]),"occult/"+std::to_string(kind),0,out);
    return out;
}
} // namespace td1::nativecas::wire
