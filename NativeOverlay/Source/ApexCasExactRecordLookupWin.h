// Included by the pinned native engine after State. EA's record writer buckets
// every non-Human kind together. Route it to the exact existing record only in
// an authenticated, detached household export; leave ordinary callers alone.
struct ExactRecordLookupScope;
inline thread_local ExactRecordLookupScope* exactRecordLookup=nullptr;
struct ExactRecordLookupScope {
    ExactRecordLookupScope* previous;
    const void* source;void* proto;std::uint64_t sim;std::uint32_t mask;
    unsigned calls=0,routed=0;std::string error;
    ExactRecordLookupScope(const void* root,void* output,std::uint64_t id,std::uint32_t membership):
        previous(exactRecordLookup),source(root),proto(output),sim(id),mask(membership) {exactRecordLookup=this;}
    ~ExactRecordLookupScope() {exactRecordLookup=previous;}
    ExactRecordLookupScope(const ExactRecordLookupScope&)=delete;
};
inline void ExportOccultRecord(void* context,std::uint32_t kind,const void* owner) {
    auto& state=Runtime();auto* scope=exactRecordLookup;
    if(!scope) {state.api.occultRecord(context,kind,owner);return;}
    // A failed native call is never replayed. The enclosing export refuses its
    // result; the normal complete wire/parser checks still run on successes.
    if(!scope->error.empty())return;
    try {
        if(!Kind(kind) || !(scope->mask&kind) || Read<std::uint64_t>(scope->source,0xb8)!=scope->sim ||
           (owner!=scope->source && owner!=Read<const void*>(scope->source,0x4c0)) ||
           Read<std::uint32_t>(owner,0xd8)!=kind || (Read<std::uint32_t>(owner,0xdc)|1u)!=scope->mask)
            throw std::runtime_error("Exact occult export lost its captured source/form identity.");
        auto* tracker=Read<void*>(Read<void*>(context));
        const auto attrs=Read<const void*>(scope->proto,0xc0);
        if(!attrs || Read<const void*>(attrs,0x90)!=tracker || (Read<std::uint32_t>(tracker,0x10)|1u)!=scope->mask)
            throw std::runtime_error("Exact occult export does not own this detached output tracker.");
        const auto count=Read<int>(tracker,0x20);
        if(count<1 || count>7)throw std::runtime_error("Exact occult export record count is incomplete.");
        auto** records=Read<void**>(tracker,0x18);Span(records,std::size_t(count)*sizeof(void*));
        std::set<std::uint32_t> seen;int exact=-1,bucket=-1;
        for(int n=0;n<count;++n) {
            if(!(Read<std::uint32_t>(records[n],0x84)&1u))throw std::runtime_error("Exact occult export record is untyped.");
            const auto current=Read<std::uint32_t>(records[n],0x18);
            if(!Kind(current) || !(scope->mask&current) || !seen.insert(current).second)
                throw std::runtime_error("Exact occult export record roster is duplicated or foreign.");
            if(current==kind)exact=n;
            if(bucket<0 && (kind==1?current==1:current!=1))bucket=n;
        }
        unsigned complete=0;for(auto value:seen)complete|=value;
        if(complete!=scope->mask || exact<0 || bucket<0)
            throw std::runtime_error("Exact occult export lost an independent form record.");
        // The native writer clears and updates the first bucket match. Swap
        // pointer positions in its detached output, then restore their order.
        // It now clears only the requested kind, retaining every other record
        // and all of its opaque/nonappearance metadata. No editor root changes.
        struct Route {
            void** records;int exact,bucket;
            Route(void** rows,int selected,int first):records(rows),exact(selected),bucket(first) {std::swap(records[exact],records[bucket]);}
            ~Route() {std::swap(records[exact],records[bucket]);}
        };
        ++scope->calls;if(exact!=bucket)++scope->routed;
        {Route route(records,exact,bucket);state.api.occultRecord(context,kind,owner);}
        if(Read<int>(tracker,0x20)!=count || Read<void**>(tracker,0x18)!=records ||
           Read<std::uint32_t>(records[exact],0x18)!=kind)
            throw std::runtime_error("Exact occult export changed its bounded record roster.");
    } catch(const std::exception& error) {scope->error=error.what();}
}
inline ui::Json ExportExactHouseholdPacket(State& state,const void* source,void* proto,std::uint64_t sim,std::uint32_t mask) {
    ExactRecordLookupScope scope(source,proto,sim,mask);
    state.api.exportProto(source,proto);
    if(!scope.error.empty())throw std::runtime_error(scope.error);
    if(!scope.calls)throw std::runtime_error("Native household export skipped its exact form record writer.");
    return {{"verified",true},{"native_calls",scope.calls},{"exact_record_routes",scope.routed},
        {"sim_id",std::to_string(sim)},{"owned_mask",mask},{"native_root_memory_written",false}};
}
