#include "../Source/ApexCasHouseholdWire.h"
#include <iostream>
#include <functional>
#include <fstream>
#include <filesystem>
#include <iterator>
#include "nlohmann/json.hpp"
using namespace td1::nativecas::wire;
void Require(bool value) {if(!value)throw std::runtime_error("Household wire contract failed.");}
void Refuses(const std::function<void()>& action) {try {action();}catch(const std::runtime_error&) {return;}throw std::runtime_error("Invalid household projection was accepted.");}
std::string Number(unsigned field,std::uint64_t value) {return Var(std::uint64_t(field)<<3)+Var(value);}
std::string Identity(std::uint64_t value) {std::string out=Var(9);for(unsigned n=0;n<8;++n)out+=char(value>>(n*8));return out;}
const std::string unknown=Var((500000000ull<<3)|3)+Number(6,123)+Var((500000000ull<<3)|4);
std::string Record(unsigned kind) {return Number(1,kind)+Bytes(11,"wrong merged body")+Number(16,99)+Number(18,kind+300)+unknown;}
std::string Packet() {
    const auto tracker=Number(1,2)+Number(2,2)+Bytes(3,Record(1))+Bytes(3,Record(2))+Number(5,1)+unknown;
    return Identity(123)+Number(8,42)+Bytes(12,"wrong active body")+Bytes(30,Bytes(11,"gameplay progression")+Bytes(17,tracker)+unknown)+unknown;
}
std::map<std::uint32_t,std::string> Owners() {
    return {{1,Identity(123)+Bytes(12,"Human body")+Bytes(18,"Human face")+Bytes(21,"Human clothing")},
            {2,Identity(123)+Bytes(12,"Alien body")+Number(10,987)+Bytes(21,"Alien clothing")+Bytes(63,"Alien pelt")}};
}
std::string Unhex(const std::string& hex) {
    if(hex.size()%2 || hex.size()>Limit*2)throw std::runtime_error("Invalid bounded native packet hex.");
    std::string out;auto digit=[](char c)->unsigned {if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;throw std::runtime_error("Invalid native packet hex digit.");};
    for(std::size_t n=0;n<hex.size();n+=2)out+=char(digit(hex[n])*16+digit(hex[n+1]));return out;
}
int main(int argc,char** argv) {
 try {
    if(argc==3) {
        if(std::filesystem::exists(argv[2]))throw std::runtime_error("Keep immutable projection outputs; choose a new file.");
        std::ifstream input(argv[1]);const auto request=nlohmann::json::parse(input);
        std::map<std::uint32_t,std::string> owners;
        for(const auto& item:request.at("owners").items())owners.emplace(static_cast<std::uint32_t>(std::stoul(item.key())),Unhex(item.value().get<std::string>()));
        const auto packet=Unhex(request.at("packet_hex"));std::string active;
        if(request.contains("unselected_active_hex"))active=Unhex(request.at("unselected_active_hex"));
        const auto projected=Household(packet,std::stoull(request.at("sim_id").get<std::string>()),request.at("owned_mask"),owners,
                                       request.contains("unselected_active_hex")?&active:nullptr);
        std::ofstream output(argv[2],std::ios::binary);output.write(projected.data(),static_cast<std::streamsize>(projected.size()));
        if(!output)throw std::runtime_error("Projection output write failed.");return 0;
    }
    const auto original=Packet();const auto owners=Owners();
    const auto projected=Household(original,123,3,owners,&owners.at(2));
    const auto root=Fields(projected);Require(One(root,12,2).value=="Alien body" && Scalar(One(root,8,0))==42);
    Require(One(root,63,2).value=="Alien pelt");
    const auto attrs=Fields(One(root,30,2).value);Require(One(attrs,11,2).value=="gameplay progression");
    const auto tracker=Fields(One(attrs,17,2).value);Require(Scalar(One(tracker,1,0))==2 && Scalar(One(tracker,2,0))==2);
    unsigned count=0;
    for(const auto& f:tracker)if(f.number==3) {
        const auto row=Fields(f.value);const auto kind=Scalar(One(row,1,0));++count;
        Require(One(row,11,2).value==(kind==1?"Human body":"Alien body"));
        Require(One(row,21,2).value==(kind==1?"Human clothing":"Alien clothing"));
        Require(Scalar(One(row,18,0))==kind+300); // Unproven/nonappearance flags stay on their actual record.
        Require(f.value.find(unknown)!=std::string::npos);
        if(kind==1) {for(const auto& item:row)Require(item.number!=16);} // Absent source defaults clear stale fields.
        else Require(Scalar(One(row,16,0))==987);
    }
    Require(count==2 && projected.find(unknown)!=std::string::npos && original==Packet());
    Require(Household(projected,123,3,owners,&owners.at(2))==projected);
    Require(Equivalent(projected,projected));
    Require(Differences(projected,projected).empty());
    const auto delta=Differences(projected,projected+Number(501,1));
    Require(delta.size()==1 && delta[0].path=="root/501" && delta[0].expected.empty());
    Require(!Equivalent(projected,projected+Number(501,1))); // Unknowns are part of qualification, not excluded.
    Require(One(Fields(Household(original,123,3,owners)),12,2).value=="wrong active body"); // Selected root stays EA-owned.
    for(const auto& broken:std::vector<std::string>{std::string(1,'\0'),std::string(1,char(0x80)),Var((4<<3)|2)+Var(99),
         Var((6<<3)|3)+Var((7<<3)|4),Var((6<<3)|4),std::string(11,char(0xff))})Refuses([&]{Fields(broken);});
    Refuses([&]{Fields(std::string(Limit+1,'x'));});
    Refuses([&]{Household(original,999,3,owners);});
    Refuses([&]{Household(original,123,7,owners);});
    Refuses([&]{auto lost=owners;lost.erase(1);Household(original,123,3,lost);});
    Refuses([&]{auto foreign=owners;foreign[1]=Identity(999);Household(original,123,3,foreign);});
    Refuses([&]{auto duplicate=owners;duplicate[1]+=Number(10,1)+Number(10,2);Household(original,123,3,duplicate);});
    Refuses([&]{Household(original+Bytes(30,"duplicate attributes"),123,3,owners);});
    Refuses([&]{const auto bad=Identity(123)+Bytes(30,Bytes(17,Number(1,2)+Bytes(3,Record(1))+Bytes(3,Record(1))));Household(bad,123,3,owners);});
    std::cout<<"Household wire isolation, defaults, unknown groups, identity and malformed-input contracts passed\n";return 0;
 }catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
