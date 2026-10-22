#pragma once
// Private P31 backend: graph-only dispatch before MUMPS analysis. Exact double
// band LDLH, conservative null detection, checked/refined work solves, lazy MUMPS.
#include <cstdio>
#include <numeric>
#include "hsolve/error.hpp"
#include "hsolve/factor.hpp"
#include "hsolve/util.hpp"
#include "band_ldlh.cpp"
namespace hs::p31 {
class Backend final : public SparseFactorization<cplx> {
  const ShiftedPencil<cplx>& pencil_;
  FactorOptions options_;
  std::vector<int> order_, inverse_;
  int width_, cap_;
  std::unique_ptr<::Factor> factor_;
  std::unique_ptr<SparseFactorization<cplx>> fallback_;
  std::vector<double> scale_;
  std::vector<cplx> original_band_;
  FactorStats own_;
  mutable FactorStats combined_;
  Inertia inertia_;
  bool detection_ = true, disabled_ = false;
  double alpha_ = 0, beta_ = 0;
  double workspace_mb() const { return (double(order()) * (cap_ + 1) * 64. + double(order()) * 256.) / 1e6; }
  void fallback(double alpha, double beta) {
    factor_.reset();
    disabled_ = true;
    if (!fallback_) {
      fallback_ = make_mumps_factorization<cplx>(options_);
      fallback_->analyze(pencil_, alpha, beta);
      std::fprintf(stderr, "P31 lazy_mumps_analysis n=%lld\n", (long long)order());
    }
    fallback_->set_null_pivot_detection(detection_);
  }
  bool factorize_impl(double alpha, double beta, bool retain) {
    if (!std::isfinite(alpha) || !std::isfinite(beta)) HS_THROW(InvalidInput, "P31 nonfinite shift");
    factor_.reset(); original_band_.clear(); inertia_ = {}; alpha_ = alpha; beta_ = beta;
    if (disabled_ || options_.out_of_core || (options_.max_memory_mb > 0 && workspace_mb() > options_.max_memory_mb)) {
      fallback(alpha, beta);
      if (retain) { bool ok = fallback_->factorize(alpha, beta); inertia_ = fallback_->inertia(); return ok; }
      inertia_ = fallback_->count(alpha, beta); return inertia_.valid;
    }
    Timer t;
    ++own_.factorizations;
    const int n = order();
    std::vector<cplx> values(pencil_.nnz());
    pencil_.assemble(alpha, beta, values.data());
    std::vector<cplx> band((size_t)n * (width_ + 1));
#pragma omp parallel for schedule(static)
    for (int i = 0; i < n; ++i) {
      for (index_t q = pencil_.rowptr()[i]; q < pencil_.rowptr()[i + 1]; ++q) {
        int r = inverse_[i], c = inverse_[pencil_.colind()[q]]; auto v = values[q];
        if (r < c) { std::swap(r, c); v = std::conj(v); }
        band[(size_t)c * (width_ + 1) + r - c] = v;
      }
    }
    if(retain) original_band_ = band;
    scale_.resize(n);
#pragma omp parallel for schedule(static)
    for (int i = 0; i < n; ++i) {
      double largest = 0;
      for (int j = std::max(0, i - width_); j <= i; ++j)
        largest = std::max(largest, std::abs(band[(size_t)j * (width_ + 1) + i - j]));
      for (int j = i + 1; j < std::min(n, i + width_ + 1); ++j)
        largest = std::max(largest, std::abs(band[(size_t)i * (width_ + 1) + j - i]));
      scale_[i] = largest > 0 ? 1 / std::sqrt(largest) : 1;
    }
#pragma omp parallel for schedule(static)
    for (int j = 0; j < n; ++j)
      for (int d = 0; d <= width_ && j + d < n; ++d)
        band[(size_t)j * (width_ + 1) + d] = (band[(size_t)j * (width_ + 1) + d] * scale_[j]) * scale_[j + d];
    auto candidate = std::make_unique<::Factor>(n, width_, cap_, band.data(), retain);
    own_.factorize_s += t.seconds();
    own_.factor_mb_used = (candidate->pool.size() * sizeof(cplx) + candidate->piv.size() * sizeof(Pivot)) / 1e6;
    own_.factor_mb_allocated = (candidate->pool.capacity() * sizeof(cplx) + candidate->piv.capacity() * sizeof(Pivot)) / 1e6;
    own_.factor_entries = 2 * (candidate->pool.size() + n);
    bool small = detection_ && candidate->minpivot <= options_.null_pivot_tol * candidate->initial;
    bool ok = candidate->status == 0 && !small;
    std::fprintf(stderr, "P31 band_factor retain=%d status=%d small=%d neg=%d relative_pivot=%.17g seconds=%.9g\n", int(retain), candidate->status, int(small), candidate->neg, candidate->minpivot/std::max(candidate->initial,1e-300),t.seconds());
    if (candidate->status == 2 || candidate->status == 3) {
      candidate.reset(); values = {}; band = {};
      fallback(alpha, beta);
      if (retain) { ok = fallback_->factorize(alpha,beta); inertia_=fallback_->inertia(); return ok; }
      inertia_ = fallback_->count(alpha,beta); return inertia_.valid;
    }
    inertia_ = {candidate->neg, ok ? 0 : 1, std::max(0,n-candidate->neg-(ok?0:1)),ok};
    own_.null_pivots = ok ? 0 : 1;
    if (ok && retain) factor_ = std::move(candidate);
    return ok;
  }
  void raw_solve(cplx* b, index_t nrhs, index_t ldb) {
    int n = order();
    std::vector<cplx> x((size_t)n * nrhs);
#pragma omp parallel for collapse(2) schedule(static)
    for (index_t r = 0; r < nrhs; ++r) for (int i = 0; i < n; ++i)
      x[r*n+i] = b[r*ldb+order_[i]] * scale_[i];
    index_t r = 0;
#if defined(__AVX512F__)
    for (; r + 4 <= nrhs; r += 4) ::solve4(*factor_, x.data()+r*n);
#endif
    if (r < nrhs) factor_->solve(x.data()+r*n, nrhs-r);
#pragma omp parallel for collapse(2) schedule(static)
    for (index_t r = 0; r < nrhs; ++r) for (int i = 0; i < n; ++i)
      b[r*ldb+order_[i]] = x[r*n+i] * scale_[i];
  }
  // Batched residual of the assembled original shifted matrix, in the same
  // permutation as the factors. The complex 1-norm denominator differs from
  // the Euclidean componentwise denominator by at most a small constant;
  // the 1e-12 internal tolerance leaves a margin to independent 1e-10 checks.
  double fast_residual(const cplx* x,index_t nrhs,index_t ldx,const std::vector<cplx>& rhs,std::vector<cplx>& r) const {
    const int n=order();std::vector<cplx> packed((size_t)n*nrhs);std::vector<double> magnitudes((size_t)n*nrhs);
    r.resize((size_t)n*nrhs);
#pragma omp parallel for schedule(static)
    for(int i=0;i<n;++i)for(index_t j=0;j<nrhs;++j){auto z=x[j*ldx+order_[i]];packed[(size_t)i*nrhs+j]=z;magnitudes[(size_t)i*nrhs+j]=std::abs(z.real())+std::abs(z.imag());}
    double worst=0;
#pragma omp parallel for schedule(static) reduction(max:worst)
    for(int i=0;i<n;++i){
      for(index_t start=0;start<nrhs;start+=8){
        const int columns=std::min<index_t>(8,nrhs-start);double sr[8]={},si[8]={},den[8]={};
        for(int j=0;j<columns;++j){auto b=rhs[(start+j)*n+order_[i]];den[j]=std::abs(b.real())+std::abs(b.imag());}
        for(int k=std::max(0,i-width_);k<std::min(n,i+width_+1);++k){
          auto v=k<=i?original_band_[(size_t)k*(width_+1)+i-k]:std::conj(original_band_[(size_t)i*(width_+1)+k-i]);
          if(v==cplx{})continue;
          double ar=v.real(),ai=v.imag(),av=std::abs(ar)+std::abs(ai);
          for(int j=0;j<columns;++j){auto z=packed[(size_t)k*nrhs+start+j];sr[j]+=ar*z.real()-ai*z.imag();si[j]+=ar*z.imag()+ai*z.real();den[j]+=av*magnitudes[(size_t)k*nrhs+start+j];}
        }
        for(int j=0;j<columns;++j){auto b=rhs[(start+j)*n+order_[i]];cplx delta=b-cplx(sr[j],si[j]);r[(start+j)*n+order_[i]]=delta;
          double eta=(std::abs(delta.real())+std::abs(delta.imag()))/std::max(den[j],std::numeric_limits<double>::min());
          worst=std::max(worst,std::isfinite(eta)?eta:std::numeric_limits<double>::infinity());}
      }
    }
    return worst;
  }
  template<class R>
  double residual(const cplx* x,index_t nrhs,index_t ldx,const std::vector<cplx>& rhs,std::vector<cplx>& r) const {
    using C=std::complex<R>;
    const auto& a=pencil_.a();const auto* b=pencil_.b();int n=order();double worst=0;
    r.resize((size_t)n*nrhs);
#pragma omp parallel for schedule(static) reduction(max:worst)
    for(int i=0;i<n;++i) for(index_t col=0;col<nrhs;++col){
      C sum{}; R denom=std::abs(C(rhs[col*n+i]));
      for(index_t q=a.rowptr[i];q<a.rowptr[i+1];++q){C v=R(alpha_)*C(a.values[q]),y=C(x[col*ldx+a.colind[q]]);sum+=v*y;denom+=std::abs(v)*std::abs(y);}
      if(b){for(index_t q=b->rowptr[i];q<b->rowptr[i+1];++q){C v=R(beta_)*C(b->values[q]),y=C(x[col*ldx+b->colind[q]]);sum+=v*y;denom+=std::abs(v)*std::abs(y);}}
      else {C y=C(x[col*ldx+i]);sum+=R(beta_)*y;denom+=std::abs(R(beta_))*std::abs(y);}
      C delta=C(rhs[col*n+i])-sum; r[col*n+i]=cplx(delta);
      double eta=double(std::abs(delta)/std::max(denom,std::numeric_limits<R>::min()));
      worst=std::max(worst,std::isfinite(eta)?eta:std::numeric_limits<double>::infinity());
    }
    return worst;
  }
 public:
  Backend(const ShiftedPencil<cplx>& p,FactorOptions o,std::vector<int> order,int width,double seconds)
    :pencil_(p),options_(std::move(o)),order_(std::move(order)),inverse_(p.order()),width_(width),cap_(std::max(16,2*width)) {
    options_.ordering=0;
    for(int i=0;i<p.order();++i)inverse_[order_[i]]=i;
    own_.analyses=1;own_.analyze_s=seconds;own_.estimate=estimate();
  }
  void analyze(const ShiftedPencil<cplx>&,double,double)override { HS_THROW(Unsupported,"P31 already analysed"); }
  FactorEstimate estimate()const override {
    if(fallback_)return fallback_->estimate();
    FactorEstimate e;e.factor_entries=2*order()*(width_+2);e.incore_mb=e.ooc_mb=workspace_mb();e.flops=8.*order()*width_*width_;return e;
  }
  bool factorize(double a,double b)override{return factorize_impl(a,b,true);}
  Inertia count(double a,double b)override{factorize_impl(a,b,false);auto result=inertia_;release_factors();return result;}
  bool has_inertia_only_count()const override{return true;}
  void solve(cplx* b,index_t nrhs,index_t ldb)override {
    if(nrhs<0||ldb<order())HS_THROW(InvalidInput,"P31 invalid RHS shape");
    if(nrhs==0)return;
    if(disabled_){fallback_->solve(b,nrhs,ldb);return;}
    HS_ASSERT(factor_&&inertia_.valid,"P31 solve without usable factors");
    if(options_.max_memory_mb>0&&double(order())*nrhs*80 > options_.max_memory_mb*1e6)
      HS_THROW(OutOfMemoryBudget,"P31 RHS workspace exceeds cap");
    Timer timer;index_t n=order();std::vector<cplx> rhs((size_t)n*nrhs),r;
    for(index_t col=0;col<nrhs;++col)std::copy_n(b+col*ldb,n,rhs.data()+col*n);
    raw_solve(b,nrhs,ldb);
    double error=fast_residual(b,nrhs,ldb,rhs,r);int steps=0;
    if(error>1e-12) {
      error=residual<long double>(b,nrhs,ldb,rhs,r);
      while(error>1e-12&&steps<3){
        raw_solve(r.data(),nrhs,n);
        for(index_t col=0;col<nrhs;++col)for(index_t i=0;i<n;++i)b[col*ldb+i]+=r[col*n+i];
        ++steps;error=residual<long double>(b,nrhs,ldb,rhs,r);
      }
    }
    if(steps)std::fprintf(stderr,"P31 refinement steps=%d eta=%.17g\n",steps,error);
    own_.solve_s+=timer.seconds();++own_.solves;own_.rhs_solved+=nrhs;
    if(!(error<=1e-12)){
      fallback(alpha_,beta_);
      if(!fallback_->factorize(alpha_,beta_))HS_THROW(FactorizationFailed,"P31 refinement fallback is singular");
      for(index_t col=0;col<nrhs;++col)std::copy_n(rhs.data()+col*n,n,b+col*ldb);
      fallback_->solve(b,nrhs,ldb);inertia_=fallback_->inertia();
      error=residual<long double>(b,nrhs,ldb,rhs,r);
      if(!(error<=1e-10))HS_THROW(FactorizationFailed,"P31 original residual failed after fallback");
    }
  }
  Inertia inertia()const override {return disabled_&&fallback_?fallback_->inertia():inertia_;}
  void set_out_of_core(bool on)override{options_.out_of_core=on;if(fallback_)fallback_->set_out_of_core(on);}
  void set_max_memory_mb(double mb)override{if(!std::isfinite(mb)||mb<0)HS_THROW(InvalidInput,"P31 invalid memory cap");options_.max_memory_mb=mb;if(fallback_)fallback_->set_max_memory_mb(mb);}
  bool release_factors()override{bool had=bool(factor_);factor_.reset();inertia_.valid=false;return (fallback_?fallback_->release_factors():false)||had;}
  void set_null_pivot_detection(bool on)override{detection_=on;if(fallback_)fallback_->set_null_pivot_detection(on);}
  const FactorOptions& options()const override{return fallback_?fallback_->options():options_;}
  index_t order()const override{return pencil_.order();}
  const std::vector<int>& pivot_order()const override{static const std::vector<int> none;return fallback_?fallback_->pivot_order():none;}
  const FactorStats& stats()const override{
    combined_=own_;if(fallback_){auto& f=fallback_->stats();combined_.analyses+=f.analyses;combined_.analyze_s+=f.analyze_s;combined_.factorizations+=f.factorizations;combined_.factorize_s+=f.factorize_s;combined_.solves+=f.solves;combined_.solve_s+=f.solve_s;combined_.rhs_solved+=f.rhs_solved;combined_.factor_mb_used=f.factor_mb_used;combined_.factor_mb_allocated=f.factor_mb_allocated;combined_.factor_entries=f.factor_entries;combined_.estimate=f.estimate;combined_.null_pivots=f.null_pivots;combined_.workspace_retries=f.workspace_retries;combined_.last_info1=f.last_info1;combined_.last_info2=f.last_info2;}return combined_;
  }
};
inline std::unique_ptr<SparseFactorization<cplx>> try_make(const ShiftedPencil<cplx>& p,const FactorOptions& options,int min_order=1000){
  Timer timer;const int n=p.order();if(n<min_order||options.precision!=FactorPrecision::Double||options.blr||options.out_of_core)return {};
  std::vector<int> offsets(n+1,0);
  for(int i=0;i<n;++i)for(index_t q=p.rowptr()[i];q<p.rowptr()[i+1];++q){int j=p.colind()[q];if(i!=j){++offsets[i+1];++offsets[j+1];}}
  for(int i=1;i<=n;++i){if(offsets[i]>64)return {};}
  std::partial_sum(offsets.begin(),offsets.end(),offsets.begin());
  std::vector<int> adj(offsets.back()),head=offsets;
  for(int i=0;i<n;++i)for(index_t q=p.rowptr()[i];q<p.rowptr()[i+1];++q){int j=p.colind()[q];if(i!=j){adj[head[i]++]=j;adj[head[j]++]=i;}}
  std::vector<int> seeds(n);std::iota(seeds.begin(),seeds.end(),0);
  auto less=[&](int i,int j){int di=offsets[i+1]-offsets[i],dj=offsets[j+1]-offsets[j];return di<dj||(di==dj&&i<j);};std::sort(seeds.begin(),seeds.end(),less);
  std::vector<char> seen(n);std::vector<int> order;order.reserve(n);std::vector<int> next;next.reserve(64);
  for(int root:seeds){if(seen[root])continue;size_t h=order.size();order.push_back(root);seen[root]=1;
    for(;h<order.size();++h){int i=order[h];next.clear();for(int q=offsets[i];q<offsets[i+1];++q){int j=adj[q];if(!seen[j]){seen[j]=1;next.push_back(j);}}std::sort(next.begin(),next.end(),less);order.insert(order.end(),next.begin(),next.end());}}
  std::reverse(order.begin(),order.end());std::vector<int> inv(n);for(int i=0;i<n;++i)inv[order[i]]=i;
  int width=0;for(int i=0;i<n;++i)for(int q=offsets[i];q<offsets[i+1];++q)width=std::max(width,std::abs(inv[i]-inv[adj[q]]));
  if(width>32)return {};
  auto f=std::make_unique<Backend>(p,options,std::move(order),width,timer.seconds());
  if(options.max_memory_mb>0&&f->estimate().incore_mb>options.max_memory_mb)return {};
  std::fprintf(stderr,"P31 fast_band_analysis n=%d width=%d seconds=%.9g\n",n,width,timer.seconds());return f;
}
}
