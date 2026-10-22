#pragma once
// Private P39: sparse block diagonalization of a matrix-verified twisted cycle.
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
namespace hs::p39 {
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
      if(!finite(value))HS_THROW(FactorizationFailed,"P39 nonfinite sector entry");
      if(value!=cplx{}){out.colind.push_back(col);out.values.push_back(value);}
    }
    out.rowptr[row+1]=out.values.size();
  }
  if(hermitian_defect(out)>1e-12)HS_THROW(FactorizationFailed,"P39 non-Hermitian Fourier sector");
  return hermitian_part(std::move(out));
}
} // namespace hs::p39
