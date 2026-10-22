// P33 private contiguous-storage experiment: band-limited Hermitian LDL^H with symmetric
// 1x1/2x2 Bunch-Kaufman pivots. Not wired into hsolve or its exact certificate.
// Pivot criteria checked against LAPACK ZHETF2 documentation:
// https://netlib.org/lapack/explore-html/db/d8d/group__hetf2_gab689426d1a589e679f8c998a6ff28bc6.html
// Independent implementation; bounded storage rejects fill instead of truncating it.
#include <algorithm>
#include <cmath>
#include <complex>
#include <limits>
#include <stdexcept>
#include <vector>
#if defined(__AVX512F__)
#include <immintrin.h>
#endif
#ifndef P36_SCHUR_SIMD
#define P36_SCHUR_SIMD 0
#endif
using Z=std::complex<double>;
static double mag(Z x){return std::abs(x.real())+std::abs(x.imag());}
struct Span { Z* data=nullptr; size_t count=0;
 Z& operator[](size_t i){return data[i];} const Z& operator[](size_t i)const{return data[i];}
 size_t size()const{return count;}
};
struct Pivot { int k,size,swap,stop; double a,c; Z b; Span l1,l2; };
struct Factor {
 int n,w,neg=0,twos=0,swaps=0,status=0,fail_k=-1,small_pivots=0; double initial=0,growth=0,minpivot=1e300;
 std::vector<Z> work,pool,swap_x,swap_y; std::vector<Pivot> piv; bool retaining;
 Z get(int i,int j) const {if(i<j)return std::conj(get(j,i));if(i-j>w)return 0.;return work[(size_t)j*(w+1)+i-j];}
 void put(int i,int j,Z x){if(i<j){put(j,i,std::conj(x));return;}if(i-j>w){if(x!=Z{})throw 2;return;}
   if(!std::isfinite(x.real())||!std::isfinite(x.imag()))throw 3;
   work[(size_t)j*(w+1)+i-j]=i==j?Z(x.real(),0):x;growth=std::max(growth,mag(x));}
 void interchange(int k,int p,int start){
   if(k==p)return; ++swaps;
   double akk=get(k,k).real(),app=get(p,p).real(); Z akp=get(k,p);
   int lo=std::max(start,std::min(k,p)-w),hi=std::min(n,std::max(k,p)+w+1);
   auto& x=swap_x;auto& y=swap_y;
   for(int j=lo;j<hi;++j){x[j-lo]=get(k,j);y[j-lo]=get(p,j);}
   // All fill must fit before doing any destructive interchange.
   for(int j=lo;j<hi;++j)if(j!=k&&j!=p){if((std::abs(k-j)>w&&y[j-lo]!=Z{})||(std::abs(p-j)>w&&x[j-lo]!=Z{}))throw 2;}
   for(int j=lo;j<hi;++j)if(j!=k&&j!=p){put(k,j,y[j-lo]);put(p,j,x[j-lo]);}
   put(k,k,app);put(p,p,akk);put(k,p,std::conj(akp));
 }
#if defined(__AVX512F__) && P36_SCHUR_SIMD
 // Four complex rows of one Schur-complement column. Pivot selection and
 // interchange retain the original scalar path. Diagonal storage stays real.
 template<bool RankTwo>
 void update_column(const Pivot& p,int j) {
   const int start=p.k+p.size;
   const Z w1=std::conj(get(j,p.k));
   const Z w2=RankTwo?std::conj(get(j,p.k+1)):Z{};
   auto scalar=[&](int i) {
     Z value=get(i,j)-p.l1[i-start]*w1;
     if constexpr(RankTwo)value-=p.l2[i-start]*w2;
     put(i,j,value);
   };
   // This is unreachable for normal bounded-band updates, but preserves the
   // scalar out-of-band zero/fill behavior instead of assuming valid storage.
   if(p.stop-1-j>w) {for(int i=j;i<p.stop;++i)scalar(i);return;}
   int i=j;
   if(i<p.stop)scalar(i++);
   const auto sign_mask=_mm512_set1_epi64(0x7fffffffffffffffLL);
   const auto finite_limit=_mm512_set1_pd(std::numeric_limits<double>::max());
   auto magnitude=[&](__m512d x) {return _mm512_castsi512_pd(_mm512_and_si512(_mm512_castpd_si512(x),sign_mask));};
   auto multiply=[](__m512d x,Z a) {
     return _mm512_fmaddsub_pd(_mm512_set1_pd(a.real()),x,
         _mm512_mul_pd(_mm512_set1_pd(a.imag()),_mm512_permute_pd(x,0x55)));
   };
   double largest=growth;
   for(;i+3<p.stop;i+=4) {
     Z* dst=work.data()+(size_t)j*(w+1)+i-j;
     const auto left=_mm512_loadu_pd(reinterpret_cast<const double*>(p.l1.data+i-start));
     auto value=_mm512_sub_pd(_mm512_loadu_pd(reinterpret_cast<const double*>(dst)),multiply(left,w1));
     if constexpr(RankTwo) {
       const auto right=_mm512_loadu_pd(reinterpret_cast<const double*>(p.l2.data+i-start));
       value=_mm512_sub_pd(value,multiply(right,w2));
     }
     const auto ab=magnitude(value);
     if(_mm512_cmp_pd_mask(ab,finite_limit,_CMP_LE_OQ)!=0xff)throw 3;
     _mm512_storeu_pd(reinterpret_cast<double*>(dst),value);
     largest=std::max(largest,_mm512_reduce_max_pd(_mm512_add_pd(ab,_mm512_permute_pd(ab,0x55))));
   }
   growth=largest;
   for(;i<p.stop;++i)scalar(i);
 }
#endif
 Factor(int nn,int bw,int cap,const Z* lower,bool keep=true,double null_tol=0):n(nn),w(cap),work((size_t)n*(w+1)),retaining(keep){
   pool.reserve(keep?(size_t)n*(w+1):(size_t)2*(w+1));if(keep)piv.reserve(n);
   swap_x.resize(2*w+1);swap_y.resize(2*w+1);
   for(int j=0;j<n;++j)for(int d=0;d<=bw&&j+d<n;++d){Z x=lower[(size_t)j*(bw+1)+d];work[(size_t)j*(w+1)+d]=x;initial=std::max(initial,mag(x));}
   growth=initial;
   constexpr double alpha=(1.+4.1231056256176605498)/8.;
   try {for(int k=0;k<n;){fail_k=k;int step=1,kp=k,imax=k;double colmax=0,akk=std::abs(get(k,k).real());
     for(int i=k+1;i<std::min(n,k+w+1);++i){double v=mag(get(i,k));if(v>colmax){colmax=v;imax=i;}}
     if(std::max(akk,colmax)==0)throw 1;
     if(akk<alpha*colmax){double rowmax=0;
       for(int j=std::max(k,imax-w);j<std::min(n,imax+w+1);++j)if(j!=imax)rowmax=std::max(rowmax,mag(get(imax,j)));
       if(akk>=alpha*colmax*(colmax/rowmax))kp=k;
       else if(std::abs(get(imax,imax).real())>=alpha*rowmax)kp=imax;
       else {step=2;kp=imax;}
     }
     interchange(k+step-1,kp,k);
     int stop=k+step;
     for(int j=k;j<k+step;++j)for(int i=k+step;i<std::min(n,j+w+1);++i)if(get(i,j)!=Z{})stop=std::max(stop,i+1);
     if(!retaining)pool.clear();
     const size_t count=stop-k-step,offset=pool.size();pool.resize(offset+count*step);
     Pivot p{k,step,kp,stop,get(k,k).real(),0,0,{pool.data()+offset,count},{}};
     if(step==2)p.l2={pool.data()+offset+count,count};
     if(step==1){double d=p.a;if(d==0||!std::isfinite(d))throw 1;neg+=d<0;minpivot=std::min(minpivot,std::abs(d));small_pivots+=std::abs(d)<=null_tol*initial;
       for(int i=k+1;i<stop;++i)p.l1[i-k-1]=get(i,k)/d;
#if defined(__AVX512F__) && P36_SCHUR_SIMD
       for(int j=k+1;j<stop;++j)update_column<false>(p,j);
#else
       for(int j=k+1;j<stop;++j)for(int i=j;i<stop;++i)put(i,j,get(i,j)-p.l1[i-k-1]*std::conj(get(j,k)));
#endif
     }else{
       ++twos;p.b=get(k+1,k);p.c=get(k+1,k+1).real();
       double s=std::max({std::abs(p.a),std::abs(p.c),std::abs(p.b)}),a=p.a/s,c=p.c/s;Z b=p.b/s;double det=a*c-std::norm(b);
       if(det==0||!std::isfinite(det))throw 1;
       neg+=det<0?1:(a+c<0?2:0);minpivot=std::min(minpivot,s*std::abs(det)/(std::abs(a)+std::abs(c)+2*std::abs(b)));
       double largest=std::abs((a+c)*.5)+std::hypot((a-c)*.5,std::abs(b));
       small_pivots+=s*largest<=null_tol*initial;small_pivots+=s*(std::abs(det)/largest)<=null_tol*initial;
       for(int i=k+2;i<stop;++i){Z u=get(i,k)/s,v=get(i,k+1)/s;p.l1[i-k-2]=(u*c-v*b)/det;p.l2[i-k-2]=(v*a-u*std::conj(b))/det;}
#if defined(__AVX512F__) && P36_SCHUR_SIMD
       for(int j=k+2;j<stop;++j)update_column<true>(p,j);
#else
       for(int j=k+2;j<stop;++j)for(int i=j;i<stop;++i)put(i,j,get(i,j)-p.l1[i-k-2]*std::conj(get(j,k))-p.l2[i-k-2]*std::conj(get(j,k+1)));
#endif
     }
     if(retaining)piv.push_back(p);k+=step;
   }fail_k=-1;}catch(int s){status=s;}
   work.clear();work.shrink_to_fit();
 }
 void solve(Z* x,int nrhs){if(status||!retaining)throw std::runtime_error("invalid factor");
   for(int rhs=0;rhs<nrhs;++rhs){Z* b=x+(size_t)n*rhs;
     for(const auto& p:piv){int k=p.k;std::swap(b[k+p.size-1],b[p.swap]);
       for(int i=k+p.size;i<p.stop;++i){int q=i-k-p.size;b[i]-=p.l1[q]*b[k];if(p.size==2)b[i]-=p.l2[q]*b[k+1];}}
     for(const auto& p:piv){int k=p.k;if(p.size==1)b[k]/=p.a;else{
       double s=std::max({std::abs(p.a),std::abs(p.c),std::abs(p.b)}),a=p.a/s,c=p.c/s;Z z=p.b/s;double det=a*c-std::norm(z);Z u=b[k]/s,v=b[k+1]/s;b[k]=(u*c-std::conj(z)*v)/det;b[k+1]=(a*v-z*u)/det;}}
     for(auto it=piv.rbegin();it!=piv.rend();++it){const auto& p=*it;int k=p.k;
       for(int i=k+p.size;i<p.stop;++i){int q=i-k-p.size;b[k]-=std::conj(p.l1[q])*b[i];if(p.size==2)b[k+1]-=std::conj(p.l2[q])*b[i];}
       std::swap(b[k+p.size-1],b[p.swap]);}
   }
 }
};
#if defined(__AVX512F__)
static inline __m512d mul4(__m512d x,Z a){
  const auto swapped=_mm512_permute_pd(x,0x55);
  return _mm512_fmaddsub_pd(_mm512_set1_pd(a.real()),x,_mm512_mul_pd(_mm512_set1_pd(a.imag()),swapped));
}
static void solve4_rows(Factor& f,Z* rows){
 if(f.status||!f.retaining)throw std::runtime_error("invalid factor");
 auto load=[&](int i){return _mm512_loadu_pd(reinterpret_cast<const double*>(rows+(size_t)i*4));};
 auto store=[&](int i,__m512d v){_mm512_storeu_pd(reinterpret_cast<double*>(rows+(size_t)i*4),v);};
 auto swap=[&](int i,int j){auto a=load(i),b=load(j);store(i,b);store(j,a);};
 for(const auto& p:f.piv){int k=p.k;swap(k+p.size-1,p.swap);auto a=load(k);
  if(p.size==1){for(int i=k+1;i<p.stop;++i)store(i,_mm512_sub_pd(load(i),mul4(a,p.l1[i-k-1])));}
  else{auto b=load(k+1);for(int i=k+2;i<p.stop;++i){int q=i-k-2;store(i,_mm512_sub_pd(_mm512_sub_pd(load(i),mul4(a,p.l1[q])),mul4(b,p.l2[q])));}}
 }
 for(const auto& p:f.piv){int k=p.k;
  if(p.size==1)store(k,_mm512_div_pd(load(k),_mm512_set1_pd(p.a)));
  else{double s=std::max({std::abs(p.a),std::abs(p.c),std::abs(p.b)}),a=p.a/s,c=p.c/s;Z z=p.b/s;double det=a*c-std::norm(z);
    auto u=_mm512_div_pd(load(k),_mm512_set1_pd(s)),v=_mm512_div_pd(load(k+1),_mm512_set1_pd(s));
    store(k,_mm512_div_pd(_mm512_sub_pd(_mm512_mul_pd(u,_mm512_set1_pd(c)),mul4(v,std::conj(z))),_mm512_set1_pd(det)));
    store(k+1,_mm512_div_pd(_mm512_sub_pd(_mm512_mul_pd(v,_mm512_set1_pd(a)),mul4(u,z)),_mm512_set1_pd(det)));
  }
 }
 for(auto it=f.piv.rbegin();it!=f.piv.rend();++it){const auto& p=*it;int k=p.k;auto a=load(k);
  if(p.size==1){for(int i=k+1;i<p.stop;++i)a=_mm512_sub_pd(a,mul4(load(i),std::conj(p.l1[i-k-1])));store(k,a);}
  else{auto b=load(k+1);for(int i=k+2;i<p.stop;++i){int q=i-k-2;auto v=load(i);a=_mm512_sub_pd(a,mul4(v,std::conj(p.l1[q])));b=_mm512_sub_pd(b,mul4(v,std::conj(p.l2[q])));}store(k,a);store(k+1,b);}
  swap(k+p.size-1,p.swap);
 }
}
static void solve4(Factor& f,Z* x){
 if(f.status||!f.retaining)throw std::runtime_error("invalid factor");
 std::vector<Z> rows((size_t)f.n*4);
 for(int i=0;i<f.n;++i)for(int r=0;r<4;++r)rows[(size_t)i*4+r]=x[(size_t)r*f.n+i];
 solve4_rows(f,rows.data());
 for(int i=0;i<f.n;++i)for(int r=0;r<4;++r)x[(size_t)r*f.n+i]=rows[(size_t)i*4+r];
}
#endif

extern "C" {
void* band_factor(int n,int bw,int cap,const Z* data,double* stats){
  if(n<=0||bw<0||cap<bw)return nullptr;
  try{auto* f=new Factor(n,bw,cap,data);stats[0]=f->status;stats[1]=f->neg;stats[2]=f->twos;stats[3]=f->swaps;stats[4]=f->fail_k;stats[5]=f->growth/std::max(f->initial,1e-300);stats[6]=f->minpivot/std::max(f->initial,1e-300);return f;}catch(...){return nullptr;}}
int band_solve(void* f,Z* b,int nrhs){try{static_cast<Factor*>(f)->solve(b,nrhs);return 0;}catch(...){return 1;}}
int band_solve_simd(void* f,Z* b,int nrhs){try{
#if defined(__AVX512F__)
 if(nrhs==4)solve4(*static_cast<Factor*>(f),b);else
#endif
 static_cast<Factor*>(f)->solve(b,nrhs);return 0;}catch(...){return 1;}}
void band_free(void* f){delete static_cast<Factor*>(f);}
}
