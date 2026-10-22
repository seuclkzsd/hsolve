#pragma once
// Private P38: sparse block diagonalization of a matrix-verified twisted cycle.
// These are candidate vectors only. The outer driver checks the original pencil
// and its unchanged exact inertia certificate. No matrix is made dense here.
#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdio>
#include <limits>
#include <string>
#include <vector>
#include "hsolve/error.hpp"
#include "hsolve/solver.hpp"
#include "hsolve/sparse.hpp"
namespace hs::p38 {
struct Cycle { index_t period=0, blocks=0; cplx wrap{}; double phase=0; };
inline cplx entry(const CsrMatrix<cplx>& a,index_t row,index_t col){
  auto begin=a.colind.begin()+a.rowptr[row],end=a.colind.begin()+a.rowptr[row+1];
  auto it=std::lower_bound(begin,end,col);
  return it!=end&&*it==col?a.values[it-a.colind.begin()]:cplx{};
}
inline bool finite(cplx z){return std::isfinite(z.real())&&std::isfinite(z.imag());}
inline bool matches(const CsrMatrix<cplx>& a,const Cycle& c){
  const double eps=64*std::numeric_limits<double>::epsilon();
  bool match=true;
#pragma omp parallel for schedule(static) reduction(&&:match)
  for(index_t row=0;row<a.nrows;++row){
    const index_t t=row%c.period,base=row-t;
    if(a.rowptr[row+1]-a.rowptr[row]!=a.rowptr[base+1]-a.rowptr[base]){match=false;continue;}
    double error=0,scale=0;
    for(index_t q=a.rowptr[row];q<a.rowptr[row+1];++q){
      const index_t col=a.colind[q],s=col%c.period,d=(s-t+c.period)%c.period;
      const cplx expected=entry(a,base,col-s+d)*(t+d>=c.period?c.wrap:cplx(1));
      match=match&&finite(a.values[q])&&finite(expected);
      error+=std::abs(a.values[q]-expected);scale+=std::abs(a.values[q]);
    }
    match=match&&std::isfinite(error)&&error<=eps*scale;
  }
  return match;
}
inline bool recognize(const CsrMatrix<cplx>& a,const CsrMatrix<cplx>* b,index_t k,Cycle& c){
  if(a.nrows<81||a.nrows!=a.ncols||k<1)return false;
  const cplx first=entry(a,0,1);
  if(first==cplx{}||!finite(first))return false;
  for(index_t period=3;period<=64;++period){
    if(a.nrows%period||a.nrows/period<std::max<index_t>(16,2*k+4))continue;
    cplx w=std::conj(entry(a,0,period-1)/first);
    if(!finite(w)||std::abs(std::abs(w)-1)>128*std::numeric_limits<double>::epsilon())continue;
    w/=std::abs(w);Cycle candidate{period,a.nrows/period,w,std::arg(w)};
    if(matches(a,candidate)&&(!b||matches(*b,candidate))){c=candidate;return true;}
  }
  return false;
}
inline CsrMatrix<cplx> sector(const CsrMatrix<cplx>& a,const Cycle& c,index_t mode){
  const double theta=(c.phase+2*std::acos(-1.)*mode)/c.period;
  std::vector<cplx> phase(c.period);
  for(index_t t=0;t<c.period;++t)phase[t]=std::polar(1.,theta*t);
  CsrMatrix<cplx> out;out.nrows=out.ncols=c.blocks;out.rowptr.assign(c.blocks+1,0);
  for(index_t row=0;row<c.blocks;++row){
    const index_t base=row*c.period;
    for(index_t q=a.rowptr[base];q<a.rowptr[base+1];){
      const index_t col=a.colind[q]/c.period;
      std::complex<long double> sum{};
      do {auto z=a.values[q],p=phase[a.colind[q]%c.period];sum+=std::complex<long double>(z.real(),z.imag())*std::complex<long double>(p.real(),p.imag());++q;}
      while(q<a.rowptr[base+1]&&a.colind[q]/c.period==col);
      cplx value(double(sum.real()),double(sum.imag()));
      if(!finite(value))HS_THROW(FactorizationFailed,"P38 nonfinite sector entry");
      if(value!=cplx{}){out.colind.push_back(col);out.values.push_back(value);}
    }
    out.rowptr[row+1]=out.values.size();
  }
  if(hermitian_defect(out)>1e-12)HS_THROW(FactorizationFailed,"P38 non-Hermitian Fourier sector");
  return hermitian_part(std::move(out));
}
inline bool candidates(const CsrMatrix<cplx>& a,const CsrMatrix<cplx>* b,const SolverConfig& parent,
                       double memory_bytes,DenseMatrix<cplx>& x,std::vector<double>& values,
                       std::vector<double>& hints,std::string& why){
  Cycle c;const index_t k=parent.target.k;
  why="no common twisted translation in A/B";
  if(!recognize(a,b,k,c))return false;
  const index_t cap=std::min<index_t>(c.blocks-1,k+2);
  const double need=64.*a.nrows*(k+cap)+192.*(a.nnz()+(b?b->nnz():0))+1048576.;
  if(!std::isfinite(memory_bytes)||memory_bytes<need){why="partial Bloch workspace budget";return false;}
  struct State { CsrMatrix<cplx> a,b;Solution<cplx> result;index_t requested=0; };
  std::vector<State> states(c.period);
  struct Pick {double value;index_t mode,column;};std::vector<Pick> picks;
  const double sigma=parent.target.sigma;
  auto calculate=[&](index_t mode,index_t wanted){
    auto& s=states[mode];
    if(s.requested==0){s.a=sector(a,c,mode);if(b)s.b=sector(*b,c,mode);}
    SolverConfig cfg=parent;
    cfg.target.k=wanted;cfg.method=Method::ShiftInvertLanczos;
    cfg.certificate=CertificateMode::Off;cfg.inertia_check=Toggle::Off;
    cfg.certificate_fault_drop=0;cfg.tol=std::min(parent.tol*.1,1e-11);
    cfg.threads=c.blocks<=4096?1:std::min(std::max(parent.threads,1),4);
    cfg.block_size=0;cfg.ncv=0;cfg.max_restarts=std::min<index_t>(parent.max_restarts,100);
    cfg.seed=parent.seed+mode;cfg.memory_budget_gb=parent.memory_budget_gb;
    s.result=Solution<cplx>{}; // release earlier vectors before another inner solve
    s.result=hs::solve(s.a,b?&s.b:nullptr,cfg);s.requested=wanted;
    const auto& result=s.result;
    std::fprintf(stderr,"P38 adaptive_sector mode=%lld period=%lld n=%lld requested=%lld pairs=%zu success=%d factors=%lld rhs=%lld seconds=%.9g\n",
      (long long)mode,(long long)c.period,(long long)c.blocks,(long long)wanted,result.eigenvalues.size(),int(result.report.success),
      (long long)result.report.factor_stats.factorizations,(long long)result.report.factor_stats.rhs_solved,result.report.time_total_s);
    if(!result.report.success||result.eigenvalues.size()<static_cast<std::size_t>(wanted))return false;
    for(double value:result.eigenvalues)if(!std::isfinite(value))return false;
    return true;
  };
  try {
    for(index_t mode=0;mode<c.period;++mode)if(!calculate(mode,std::min<index_t>(2,cap))){why="partial Bloch preliminary solve failed";return false;}
    while(true){
      picks.clear();
      for(index_t mode=0;mode<c.period;++mode){
        const auto& w=states[mode].result.eigenvalues;
        for(index_t j=0;j<static_cast<index_t>(w.size());++j)picks.push_back({w[j],mode,j});
      }
      std::stable_sort(picks.begin(),picks.end(),[&](const Pick& l,const Pick& r){return std::abs(l.value-sigma)<std::abs(r.value-sigma);});
      const double radius=picks.size()>=static_cast<std::size_t>(k)?std::abs(picks[k-1].value-sigma):std::numeric_limits<double>::infinity();
      const double margin=64*std::numeric_limits<double>::epsilon()*std::max(std::abs(sigma),radius);
      bool expanded=false;
      for(index_t mode=0;mode<c.period;++mode){
        auto& s=states[mode];if(s.requested>=cap)continue;
        double tail=0;for(double v:s.result.eigenvalues)tail=std::max(tail,std::abs(v-sigma));
        // Preliminary modal values only decide where to request more candidates.
        // They are never used to certify exclusion from the original spectrum.
        if(picks.size()<static_cast<std::size_t>(k)||tail<=radius+margin){
          if(!calculate(mode,std::min(cap,2*s.requested))){why="partial Bloch expansion failed";return false;}
          expanded=true;
        }
      }
      if(!expanded)break;
    }
  } catch(const Error& error){
    if(error.code()!=Error::Code::NotConverged&&error.code()!=Error::Code::FactorizationFailed&&
       error.code()!=Error::Code::Singular&&error.code()!=Error::Code::OutOfMemoryBudget)throw;
    why=std::string("partial Bloch inner solve rejected: ")+error.what();return false;
  }
  if(picks.size()<static_cast<std::size_t>(k)){why="not enough partial Bloch candidates";return false;}
  x=DenseMatrix<cplx>(a.nrows,k);values.resize(k);hints.clear();
  for(const auto& pick:picks)hints.push_back(pick.value);
  for(index_t j=0;j<k;++j){
    const auto& pick=picks[j];values[j]=pick.value;
    const double theta=(c.phase+2*std::acos(-1.)*pick.mode)/c.period;
    for(index_t t=0;t<c.period;++t){
      const cplx weight=std::polar(1/std::sqrt(double(c.period)),theta*t);
      for(index_t g=0;g<c.blocks;++g)x(g*c.period+t,j)=weight*states[pick.mode].result.eigenvectors(g,pick.column);
    }
  }
  why="matrix-verified adaptive partial Bloch translation; period="+std::to_string(c.period)+" block_order="+std::to_string(c.blocks);
  return true;
}
} // namespace hs::p38
