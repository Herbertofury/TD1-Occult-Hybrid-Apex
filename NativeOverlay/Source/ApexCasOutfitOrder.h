#pragma once
#include <map>
#include <set>
#include <vector>
#include <stdexcept>

namespace td1::nativecas::outfitorder {
// EA inserts copied categories at the head of a hash chain. A complete deep
// copy can therefore reverse colliding categories without changing any outfit.
// Keep the exact source traversal in an independently owned destination. Plan
// and validate every link first; never modify source nodes or outfit payloads.
template<class Node,class Key,class Next,class Link,class Head>
void Preserve(const std::vector<Node>& source,const std::vector<Node>& target,
              unsigned sourceCount,unsigned targetCount,Key key,Next next,Link link,Head head) {
    if(source.empty() || source.size()>4096 || source.size()!=target.size() ||
       sourceCount>14 || targetCount!=sourceCount)
        throw std::runtime_error("Outfit category map shape changed during its detached copy.");
    std::set<Node> originals,copies;std::set<unsigned> keys;
    std::vector<std::vector<unsigned>> wanted(source.size());std::map<unsigned,Node> available;
    for(std::size_t bucket=0;bucket<source.size();++bucket) {
        for(Node node=source[bucket];node!=Node{};node=next(node)) {
            if(!originals.insert(node).second || originals.size()>sourceCount)
                throw std::runtime_error("Source outfit category chain is cyclic or duplicated.");
            const auto category=key(node);
            if(category>13 || category%source.size()!=bucket || !keys.insert(category).second)
                throw std::runtime_error("Source outfit category identity or bucket is invalid.");
            wanted[bucket].push_back(category);
        }
        for(Node node=target[bucket];node!=Node{};node=next(node)) {
            if(!copies.insert(node).second || copies.size()>targetCount)
                throw std::runtime_error("Destination outfit category chain is cyclic or duplicated.");
            const auto category=key(node);
            if(category>13 || category%target.size()!=bucket || !available.emplace(category,node).second)
                throw std::runtime_error("Destination outfit category identity or bucket is invalid.");
        }
    }
    if(originals.size()!=sourceCount || copies.size()!=targetCount || keys.size()!=available.size())
        throw std::runtime_error("Detached outfit category inventory is incomplete.");
    if(!sourceCount)return; // Empty maps may share EA's immutable empty buckets.
    for(const auto& row:available)
        if(!keys.count(row.first) || originals.count(row.second))
            throw std::runtime_error("Detached outfit categories differ or alias their source.");
    std::vector<std::vector<Node>> planned(wanted.size());
    for(std::size_t bucket=0;bucket<wanted.size();++bucket)
        for(auto category:wanted[bucket])planned[bucket].push_back(available.at(category));
    for(std::size_t bucket=0;bucket<planned.size();++bucket) {
        const auto& nodes=planned[bucket];
        for(std::size_t n=0;n<nodes.size();++n)link(nodes[n],n+1<nodes.size()?nodes[n+1]:Node{});
        head(bucket,nodes.empty()?Node{}:nodes.front());
    }
}
}
