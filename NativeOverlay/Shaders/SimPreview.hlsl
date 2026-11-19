// Device-independent preview shaders, compiled during the build, never when
// a player changes Sim, form, outfit or CC. Skinning stays on the GPU.
cbuffer C : register(b0) {
    row_major float4x4 view;
    row_major float4x4 joints[256];
    float4 light;
};
Texture2D diffuse : register(t0);
SamplerState sampleState : register(s0);
struct V { float3 p:POSITION; float3 n:NORMAL; float2 uv:TEXCOORD; uint4 j:BLENDINDICES; float4 w:BLENDWEIGHT; };
struct P { float4 p:SV_POSITION; float3 n:NORMAL; float2 uv:TEXCOORD; };
P VS(V v) {
    P o; float4 p=0; float3 n=0;
    [unroll] for(int i=0;i<4;i++) {
        p+=mul(float4(v.p,1),joints[v.j[i]])*v.w[i];
        n+=mul(float4(v.n,0),joints[v.j[i]]).xyz*v.w[i];
    }
    o.p=mul(p,view);o.n=normalize(n);o.uv=v.uv;return o;
}
float4 PS(P p):SV_TARGET {
    float4 c=diffuse.Sample(sampleState,p.uv);clip(c.a-.025);
    float3 n=normalize(p.n);
    float lit=.5+.5*max(0,dot(n,normalize(float3(-.4,.7,.8))));
    lit+=.15*max(0,dot(n,normalize(float3(.8,.2,-.6))));
    return float4(saturate(c.rgb*lit*light.x),c.a);
}
