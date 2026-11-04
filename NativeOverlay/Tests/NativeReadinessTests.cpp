#define main ExistingNativeContracts
#include "NativeCasEngineTests.cpp"
#undef main
unsigned readyNativeSaves=0,readySyncs=0;bool readyBusy=true;
bool ReadinessBusy(void*){return readyBusy;}
bool ReadinessOriginalSave(const void* arg){++readyNativeSaves;BoolValue(Read<void*>(arg,0x10),true);return true;}
void ReadinessSync(void*){++readySyncs;}
void ReadinessClothing(void* model,bool value){ClothingPreview(model,value);if(!value)readyBusy=true;}
void* readinessMutationTarget=nullptr;
void ReadinessMutateOtherOwner(void* output,const void* input){
 AssignData(output,input);
 if(output==readinessMutationTarget){auto& other=Runtime().bank.at(13);other.graph->select(other.graph->cursor(),"native/1");}
}
std::map<std::string,std::array<char,16>> preparedMembers;
bool HasPreparedMember(const void*,const char* name){return preparedMembers.count(name)!=0;}
const void* PreparedMember(const void*,const char* name){return preparedMembers.at(name).data();}
struct OwnedGfxString {
 std::string text;std::array<char,16> object{},value{};
 explicit OwnedGfxString(std::string s):text(std::move(s)){
  Write(object.data(),0,text.c_str());Write(object.data(),8,static_cast<std::uint32_t>(text.size()));object[15]=char(128);
  Write(value.data(),0,6u);Write(value.data(),8,object.data());
 }
};
int main(){try{
 Require(ExistingNativeContracts()==0);
 auto& s=Runtime();s.bank.clear();s.scope.members.clear();s.scope.id.clear();s.armed=false;s.selectionEnabled=false;
 s.acceptReadiness={};s.nativeSaveSerial=0;s.cancelSerial=0;s.sessionsRetired=0;s.installed=true;
 auto* image=static_cast<char*>(VirtualAlloc(nullptr,0x2967000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));Require(image);
 s.image=reinterpret_cast<std::uintptr_t>(image);
 std::array<char,0x250> controller{};std::array<char,0x830> group{};std::array<char,0xc40> model{};
 std::array<char,0x40> node{},wrapper{};std::array<char,0x50> phase{};std::array<char,0x400> proto{};sourceProto=proto.data();
 Write(image,0x2948f00,controller.data());Write(image,0x2965870,wrapper.data());Write(wrapper.data(),0x18,phase.data());
 Write(controller.data(),0,s.image+0x1e78f38);Write(controller.data(),0xb0,std::uint64_t(34));
 Write(controller.data(),0x100,group.data());Write(controller.data(),0x1d0,model.data());
 Write(controller.data(),0x108,node.data());Write(node.data(),0,controller.data()+0x108);Write(node.data(),0x10,group.data());
 Write(group.data(),0x10,importEntityTable.data());Write(group.data(),0xb8,std::uint64_t(12));
 Write(group.data(),0x640,std::uint64_t(34));Write(group.data(),0xd8,4u);Write(group.data(),0xdc,127u);
 Write(group.data(),0x700,std::uint64_t(0x101010101));
 Write(model.data(),0,s.image+0x1e83970);Write(image,0x1e83970+0x308,s.image+0x44e880);
 Write(model.data(),0x178,2u);Write(model.data(),0x17c,127u);Write(model.data(),0xa60,std::uint8_t(1));
 s.api.assignSim=CopySim;s.api.modelBusy=ReadinessBusy;s.api.hairPreview=HairPreview;s.api.clothingPreview=ClothingPreview;s.api.wingsPreview=WingsPreview;
 s.api.saveAndExit=ReadinessOriginalSave;s.api.sync=ReadinessSync;s.api.boolValue=BoolValue;
 s.api.valueHasMember=HasPreparedMember;s.api.valueMember=PreparedMember;
 std::array<char,32> argument{};std::array<char,16> result{},object{};Write(object.data(),0,7u);
 Write(argument.data(),8,object.data());Write(argument.data(),0x10,result.data());
 const auto nonce=std::string(64,'a');
 auto request=[&](char c){return std::string(32,c)+"|"+nonce+"|12|34|0|0|4|2|127|-|0";};
 auto begin=[&](char c){return AcceptReadinessCommand(s,"APEXACCEPT1|PREPARE|"+request(c));};
 auto poll=[&](char c){return AcceptReadinessCommand(s,"APEXACCEPT1|READY|"+request(c));};
 Require(begin('b').rfind("ACCEPTSTATE|WAIT|",0)==0);Require(readyNativeSaves==0 && readySyncs==0);
 const auto exportsBefore=protoDestroyed,clonesBefore=destroyed;
 for(int frame=0;frame<50;++frame)Require(poll('b').rfind("ACCEPTSTATE|WAIT|",0)==0);
 Require(protoDestroyed==exportsBefore && destroyed==clonesBefore); // Busy waits: ZERO complete clones/exports.

 readyBusy=false;Write(phase.data(),0x40,1u);Require(poll('b').rfind("ACCEPTSTATE|WAIT|",0)==0);
 Write(phase.data(),0x40,0u);Require(poll('b').rfind("ACCEPTSTATE|READY|",0)==0);Require(protoDestroyed==exportsBefore+1 && destroyed==clonesBefore+1);
 OwnedGfxString id(std::string(32,'b')),owner(nonce);preparedMembers["apex_accept_id"]=id.value;preparedMembers["apex_accept_nonce"]=owner.value;
 Require(SaveAndExit(argument.data()));Require(readyNativeSaves==1 && readySyncs==0 && s.nativeSaveSerial==1);
 Require(protoDestroyed==exportsBefore+2 && destroyed==clonesBefore+2); // Consume repeats complete fresh proof.
 Require(SaveAndExit(argument.data()));Require(readyNativeSaves==1 && s.nativeSaveSerial==1); // Exact receipt never replays.
 // Whole appearance and unknown ROOT bytes both invalidate the retained digest.
 begin('c');Write(model.data(),0x3c0,0x12345678u);Refuses([&]{poll('c');});Write(model.data(),0x3c0,0u);
 begin('d');Write(group.data(),0x700,std::uint64_t(0x202020202));Refuses([&]{poll('d');});
 begin('e');Write(phase.data(),0x40,3u);Require(poll('e').rfind("ACCEPTSTATE|WAIT|",0)==0);Write(phase.data(),0x40,0u);
 AcceptReadinessCommand(s,"APEXACCEPT1|CANCEL|"+request('e'));Refuses([&]{poll('e');});
 begin('f');Write(controller.data(),0xb0,std::uint64_t(35));Refuses([&]{poll('f');});Write(controller.data(),0xb0,std::uint64_t(34));
 // Untyped manual entry remains available; the failed typed ticket cannot block it.
 preparedMembers.clear();Require(SaveAndExit(argument.data()));Require(readyNativeSaves==2 && s.nativeSaveSerial==2);

 // A retired/inactive previous Apex scope is not a fabricated owner in a
 // later plain room. Its identity is fenced, but missing retired graphs do not
 // block the existing unbound editor.
 s.scope.id=std::string(32,'9');s.scope.members.emplace(99,Member{99,3});s.scopeRetired=true;s.armed=true;
 Require(begin('0').rfind("ACCEPTSTATE|READY|",0)==0);s.scope.members.clear();s.scopeRetired=false;
 // Actual captured graph: PREPARE performs one authoritative harvest; typed
 // Save repairs/compares canonical caches but MUST NOT call Sync again.
 s.scope.id=std::string(32,'a');s.scope.members.emplace(12,Member{12,127});s.armed=true;s.selectionEnabled=true;
 auto& bank=s.bank[12];bank.mask=127;bank.viewBound=true;bank.boundGroup=group.data();bank.seeded=true;bank.editorImported=true;bank.importedEntity=12;
 for(unsigned kind:{1u,2u,4u,8u,16u,32u,64u}) {
  auto owned=std::make_unique<NativeOwner>(s.api,12);s.api.current(owned->value,kind);s.api.availableData(const_cast<void*>(owned->data()),127);
  bank.owners.emplace(kind,std::move(owned));bank.logicalOwners.emplace(kind,NativeOwnerId(kind));
 }
 bank.graph=std::make_unique<OwnerGraph<std::unique_ptr<NativeOwner>>>(12,127,2,bank.owners,[&](const auto& from,unsigned kind){
  auto copy=std::make_unique<NativeOwner>(s.api,*from);s.api.current(copy->value,kind);return copy;});
 s.boundSim=12;s.boundController=controller.data();
 Write(group.data(),0xd8,4u);Write(group.data(),0xdc,127u);Write(model.data(),0x178,2u);Write(model.data(),0x17c,127u);
 Cache cache;std::array<char,0x38> metadata{};Write(metadata.data(),8,&cache);viewMetadata=metadata.data();
 Write(image,0x1e78f38+0x410,reinterpret_cast<void*>(&NativeCache));
 s.api.index=NativeIndex;s.api.prepareHousehold=[](void*){
  // The all-seven-owner fixture crosses the existing independent-hybrid
  // household guard. Represent that separate API's fresh receipt explicitly;
  // its complete native copy behavior is covered by the engine tests above.
  auto& state=Runtime();for(auto& row:state.bank)if(row.second.editorImported)
   row.second.householdCanonical={{"prepared",true},{"scope_id",state.scope.id},{"generation",row.second.graph->cursor().generation}};
 };s.api.clothingPreview=ReadinessClothing;
 Write(model.data(),0xbb9,std::uint8_t(1));Write(model.data(),0xb20,0x777u);readyBusy=false;
 // Actual hybrid layout: shell4, rendered owner2. Sync legitimately replaces
 // only the selected shell with owner2; it must not fail the before/after
 // identity or permit an arbitrary original kind to be adopted.
 const auto wrongOriginal=std::string(32,'a')+"|"+nonce+"|12|34|0|0|8|2|127|-|0";
 Refuses([&]{AcceptReadinessCommand(s,"APEXACCEPT1|PREPARE|"+wrongOriginal);});
 Require(bank.canonicalWrites==0 && Read<unsigned>(group.data(),0xd8)==4);
 const auto capturedRequest=std::string(32,'1')+"|"+nonce+"|12|34|0|0|4|2|127|-|0";
 Require(AcceptReadinessCommand(s,"APEXACCEPT1|PREPARE|"+capturedRequest).rfind("ACCEPTSTATE|WAIT|",0)==0);
 Require(bank.canonicalWrites==1 && !bank.viewFault && Read<unsigned>(model.data(),0x3c0)==0x777);
 Require(Read<unsigned>(group.data(),0xd8)==2 && Read<unsigned>(group.data(),0xdc)==127);
 const auto preparedGeneration=bank.graph->cursor().generation;readyBusy=false;
 Require(AcceptReadinessCommand(s,"APEXACCEPT1|READY|"+capturedRequest).rfind("ACCEPTSTATE|READY|",0)==0);
 OwnedGfxString capturedId(std::string(32,'1'));preparedMembers["apex_accept_id"]=capturedId.value;preparedMembers["apex_accept_nonce"]=owner.value;
 Require(SaveAndExit(argument.data()));Require(readyNativeSaves==3 && bank.canonicalWrites==2 && bank.graph->cursor().generation==preparedGeneration);
 Require(s.householdAcceptance.value("verified",false));Require(SaveAndExit(argument.data()));Require(readyNativeSaves==3 && bank.canonicalWrites==2);
 // Same-generation scalar-state changes refuse before any further full read.
 const auto noMoreSaves=readyNativeSaves;
 for(int which=0;which<4;++which) {
  const auto req=std::string(32,char('2'+which))+"|"+nonce+"|12|34|0|0|2|2|127|-|0";
  Require(AcceptReadinessCommand(s,"APEXACCEPT1|PREPARE|"+req).rfind("ACCEPTSTATE|READY|",0)==0);
  const auto beforeExports=protoDestroyed,beforeClones=destroyed;
  if(which==0)bank.viewFault=true;else if(which==1)s.boundSim=99;else if(which==2)bank.editorImported=false;else bank.boundContext=reinterpret_cast<void*>(0x10000);
  Refuses([&]{AcceptReadinessCommand(s,"APEXACCEPT1|READY|"+req);});
  Require(protoDestroyed==beforeExports && destroyed==beforeClones && readyNativeSaves==noMoreSaves);
  bank.viewFault=false;s.boundSim=12;bank.editorImported=true;bank.boundContext=nullptr;
  Refuses([&]{AcceptReadinessCommand(s,"APEXACCEPT1|READY|"+req);}); // No recovery/replay of original ticket.
 }
 // Preparation-compatible normalization never weakens the ACTUAL retained
 // scalar stamp. Reverting to the original shell, or a different mask, after
 // preparation must refuse before any complete cloning/native save.
 for(int which=0;which<2;++which) {
  const auto req=std::string(32,char('6'+which))+"|"+nonce+"|12|34|0|0|2|2|127|-|0";
  Require(AcceptReadinessCommand(s,"APEXACCEPT1|PREPARE|"+req).rfind("ACCEPTSTATE|READY|",0)==0);
  const auto beforeExports=protoDestroyed,beforeClones=destroyed;
  if(which==0)Write(group.data(),0xd8,4u);else Write(group.data(),0xdc,63u);
  Refuses([&]{AcceptReadinessCommand(s,"APEXACCEPT1|READY|"+req);});
  Require(protoDestroyed==beforeExports && destroyed==beforeClones && readyNativeSaves==noMoreSaves);
  Write(group.data(),0xd8,2u);Write(group.data(),0xdc,127u);
  Refuses([&]{AcceptReadinessCommand(s,"APEXACCEPT1|READY|"+req);});
 }
 // A mismatched original mask is not an authorized shell normalization.
 Write(group.data(),0xd8,4u);Write(group.data(),0xdc,63u);
 const auto wrongMask=std::string(32,'8')+"|"+nonce+"|12|34|0|0|4|2|63|-|0";
 Refuses([&]{AcceptReadinessCommand(s,"APEXACCEPT1|PREPARE|"+wrongMask);});
 Require(readyNativeSaves==noMoreSaves);
 // Normalizing the selected shell must NEVER normalize another captured
 // member's edit/generation during the same native preparation callback.
 Write(group.data(),0xd8,4u);Write(group.data(),0xdc,127u);
 s.scope.members.emplace(13,Member{13,127});auto& other=s.bank[13];other.mask=127;
 for(unsigned kind:{1u,2u,4u,8u,16u,32u,64u}){
  auto owned=std::make_unique<NativeOwner>(s.api,13);s.api.current(owned->value,kind);s.api.availableData(const_cast<void*>(owned->data()),127);
  other.owners.emplace(kind,std::move(owned));
 }
 other.graph=std::make_unique<OwnerGraph<std::unique_ptr<NativeOwner>>>(13,127,2,other.owners,[&](const auto& from,unsigned kind){
  auto copy=std::make_unique<NativeOwner>(s.api,*from);s.api.current(copy->value,kind);return copy;});
 readinessMutationTarget=group.data()+0xd0;s.api.assignData=ReadinessMutateOtherOwner;
 const auto otherMutation=std::string(32,'9')+"|"+nonce+"|12|34|0|0|4|2|127|-|0";
 Refuses([&]{AcceptReadinessCommand(s,"APEXACCEPT1|PREPARE|"+otherMutation);});
 Require(other.graph->cursor().kind==1 && readyNativeSaves==noMoreSaves);
 s.api.assignData=AssignData;readinessMutationTarget=nullptr;
 s.bank.clear();s.scope.members.clear();s.selectionEnabled=false;s.armed=false;
 Require(VirtualFree(image,0,MEM_RELEASE));s.image=0;s.installed=false;
 std::cout<<"Real EngineWin readiness/complete-model+root bytes/typed-save/once-only/manual contracts passed\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
