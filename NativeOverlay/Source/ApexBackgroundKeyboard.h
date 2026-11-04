#pragma once
namespace td1 {
inline bool NavigationKey(int key) {
    return key==9||key==13||key==27||key==32||(key>=33&&key<=40)||key==122;
}
template<class Valid,class Owned,class Post,class Wait>
int RunBackgroundKey(int key,Valid valid,Owned owned,Post post,Wait wait) {
    if(!NavigationKey(key))return -4;
    if(!valid())return -8;
    if(!post(key,true))return -5;
    wait(24);
    // Always release a posted key while the exact game window still belongs
    // to this process, including a resize between down and up.
    if(!owned()||!post(key,false))return -5;
    return valid()?4:-8;
}
}
