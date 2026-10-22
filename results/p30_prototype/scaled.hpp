#pragma once
// Private P30 scaled band variant: positive diagonal congruence, band work and
// endpoint counts, small/failed pivots fall back to original MUMPS. NOT production.
#include <numeric>
#include <cstdio>
#include "hsolve/factor.hpp"
#include "hsolve/util.hpp"
#include "hsolve/error.hpp"
#include "band_ldlh.cpp"
namespace hs::p30 {
class Hybrid final:public SparseFactorization<cplx>{
 std::unique_ptr<SparseFactorization<cplx>> base;
 const ShiftedPencil<cplx>& pencil;
 std::vector<int> order_,inverse;int width=0,cap=0;
 std::unique_ptr<::Factor> factor;
 std::vector<double> scale;
 FactorStats extra;mutable FactorStats combined;Inertia current;bool detection=true,ours=false;
 public:
 Hybrid(std::unique_ptr<SparseFactorization<cplx>> f,const ShiftedPencil<cplx>& p,std::vector<int> o,int w,double prepare):base(std::move(f)),pencil(p),order_(std::move(o)),inverse(p.order()),width(w),cap(std::max(64,4*w)){
  for(int i=0;i<p.order();++i)inverse[order_[i]]=i;extra.analyze_s=prepare;
 }
 void analyze(const ShiftedPencil<cplx>&,double,double) override {HS_THROW(Unsupported,"P30 private wrapper is already analysed");}
 FactorEstimate estimate()const override{return base->estimate();}
 bool factorize(double alpha,double beta)override{
  factor.reset();ours=false;
  const int n=order_.size();const double bytes=double(n)*(cap+1)*64+double(n)*256;
  if(!options().out_of_core&&(options().max_memory_mb==0||bytes<options().max_memory_mb*1e6)){
   Timer t;std::vector<cplx> values(pencil.nnz());pencil.assemble(alpha,beta,values.data());std::vector<cplx> band((size_t)n*(width+1));
   for(int i=0;i<n;++i)for(index_t q=pencil.rowptr()[i];q<pencil.rowptr()[i+1];++q){int r=inverse[i],c=inverse[pencil.colind()[q]];auto v=values[q];if(r<c){std::swap(r,c);v=std::conj(v);}band[(size_t)c*(width+1)+r-c]=v;}
   scale.assign(n,0.0);
   for(int j=0;j<n;++j)for(int d=0;d<=width&&j+d<n;++d){double v=std::abs(band[(size_t)j*(width+1)+d]);scale[j]=std::max(scale[j],v);scale[j+d]=std::max(scale[j+d],v);}
   for(double& v:scale)v=v>0?1/std::sqrt(v):1.;
   for(int j=0;j<n;++j)for(int d=0;d<=width&&j+d<n;++d)band[(size_t)j*(width+1)+d]*=scale[j]*scale[j+d];
   auto trial=std::make_unique<::Factor>(n,width,cap,band.data());
   bool valid=trial->status==0 && (!detection||trial->minpivot>options().null_pivot_tol*trial->initial);
   extra.factorize_s+=t.seconds();
   std::fprintf(stderr,"P30 scaled_band_factor status=%d accepted=%d relative_pivot=%.17g neg=%d\n",trial->status,int(valid),trial->minpivot/std::max(trial->initial,1e-300),trial->neg);
   if(valid){base->release_factors();factor=std::move(trial);ours=true;++extra.factorizations;current={factor->neg,0,n-factor->neg,true};return true;}
  }
  bool ok=base->factorize(alpha,beta);current=base->inertia();return ok;
 }
 Inertia count(double alpha,double beta)override{
  // Separate experimental variant: same pivoted LDLH for counts, conservative
  // small-pivot rejection falls through to the original MUMPS factorization.
  factorize(alpha,beta);Inertia result=inertia();release_factors();return result;
 }
 bool has_inertia_only_count()const override{return true;}
 void solve(cplx* b,index_t nrhs,index_t ldb)override{
  if(!ours){base->solve(b,nrhs,ldb);return;}
  HS_ASSERT(factor&&current.valid,"P30 solve without factors");const int n=order_.size();Timer t;std::vector<Z> x((size_t)n*nrhs);
  for(int r=0;r<nrhs;++r)for(int i=0;i<n;++i)x[(size_t)r*n+i]=b[r*ldb+order_[i]]*scale[i];
  int r=0;
#if defined(__AVX512F__)
  for(;r+4<=nrhs;r+=4)::solve4(*factor,x.data()+(size_t)r*n);
#endif
  if(r<nrhs)factor->solve(x.data()+(size_t)r*n,nrhs-r);
  for(int r=0;r<nrhs;++r)for(int i=0;i<n;++i)b[r*ldb+order_[i]]=x[(size_t)r*n+i]*scale[i];
  extra.solve_s+=t.seconds();++extra.solves;extra.rhs_solved+=nrhs;
 }
 Inertia inertia()const override{return ours?current:base->inertia();}
 void set_out_of_core(bool on)override{base->set_out_of_core(on);}
 void set_max_memory_mb(double mb)override{base->set_max_memory_mb(mb);}
 bool release_factors()override{bool held=bool(factor);factor.reset();ours=false;current.valid=false;return base->release_factors()||held;}
 void set_null_pivot_detection(bool on)override{detection=on;base->set_null_pivot_detection(on);}
 const FactorOptions& options()const override{return base->options();}
 index_t order()const override{return pencil.order();}
 const std::vector<int>& pivot_order()const override{return base->pivot_order();}
 const FactorStats& stats()const override{
  combined=base->stats();combined.analyze_s+=extra.analyze_s;combined.factorize_s+=extra.factorize_s;combined.solve_s+=extra.solve_s;
  combined.factorizations+=extra.factorizations;combined.solves+=extra.solves;combined.rhs_solved+=extra.rhs_solved;
  if(ours){std::int64_t entries=0;for(const auto& p:factor->piv)entries+=p.l1.size()+p.l2.size()+p.size;
   combined.factor_entries=2*entries;combined.factor_mb_used=(entries*16.+factor->piv.size()*sizeof(Pivot))/1e6;combined.factor_mb_allocated=combined.factor_mb_used;combined.null_pivots=0;}
  return combined;
 }
};
inline std::unique_ptr<SparseFactorization<cplx>> wrap(std::unique_ptr<SparseFactorization<cplx>> f,const ShiftedPencil<cplx>& p){
 Timer t;const int n=p.order();if(n<1000||f->options().precision!=FactorPrecision::Double||f->options().blr||f->options().out_of_core)return f;
 std::vector<std::vector<int>> adj(n);for(int i=0;i<n;++i)for(index_t q=p.rowptr()[i];q<p.rowptr()[i+1];++q){int j=p.colind()[q];if(i!=j){adj[i].push_back(j);adj[j].push_back(i);}}
 std::vector<int> seeds(n);std::iota(seeds.begin(),seeds.end(),0);auto less=[&](int i,int j){return adj[i].size()<adj[j].size()||(adj[i].size()==adj[j].size()&&i<j);};std::sort(seeds.begin(),seeds.end(),less);
 std::vector<char> seen(n);std::vector<int> order;order.reserve(n);std::vector<int> next;
 for(int root:seeds){if(seen[root])continue;size_t head=order.size();order.push_back(root);seen[root]=1;
  for(;head<order.size();++head){next.clear();for(int j:adj[order[head]])if(!seen[j]){seen[j]=1;next.push_back(j);}std::sort(next.begin(),next.end(),less);order.insert(order.end(),next.begin(),next.end());}}
 std::reverse(order.begin(),order.end());std::vector<int> inv(n);for(int i=0;i<n;++i)inv[order[i]]=i;
 int width=0;for(int i=0;i<n;++i)for(int j:adj[i])width=std::max(width,std::abs(inv[i]-inv[j]));
 if(width>32)return f;
 std::fprintf(stderr,"P30 band_prepare n=%d width=%d seconds=%.9g\n",n,width,t.seconds());
 return std::make_unique<Hybrid>(std::move(f),p,std::move(order),width,t.seconds());
}
}
