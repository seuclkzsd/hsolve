  // SIMD double-double residual for the first refinement correction only.
  // The unchanged original-pencil long-double residual still decides acceptance.
  // Extreme coefficients/vectors use that reference path directly.
  double correction_residual(const cplx* x,index_t nrhs,index_t ldx,
      const std::vector<cplx>& rhs,std::vector<cplx>& r,bool* vectorized=nullptr) const {
    if(vectorized)*vectorized=false;
#if defined(__AVX512F__)
    const int n=order();const auto& a=pencil_.a();const auto* b=pencil_.b();
    auto supported=[](double v){return v==0. || (std::isfinite(v)&&std::abs(v)>=1e-100&&std::abs(v)<=1e100);};
    std::vector<cplx> packed((size_t)n*nrhs);r.resize((size_t)n*nrhs);
    int unsafe=0;
#pragma omp parallel for schedule(static) reduction(|:unsafe)
    for(int i=0;i<n;++i)for(index_t j=0;j<nrhs;++j){
      auto z=x[j*ldx+i],v=rhs[j*n+i];packed[(size_t)i*nrhs+j]=z;
      unsafe|=!(supported(z.real())&&supported(z.imag())&&supported(v.real())&&supported(v.imag()));
    }
    if(unsafe)return residual<long double>(x,nrhs,ldx,rhs,r);
    double worst=0;
#pragma omp parallel for schedule(static) reduction(max:worst) reduction(|:unsafe)
    for(int i=0;i<n;++i)for(index_t start=0;start<nrhs;start+=4){
      const int columns=std::min<index_t>(4,nrhs-start);
      const __mmask8 mask=static_cast<__mmask8>((1u<<(2*columns))-1u);
      const auto zero=_mm512_setzero_pd();auto hi=zero,lo=zero;
      const auto abs_mask=_mm512_set1_epi64(0x7fffffffffffffffLL);
      auto absvec=[&](__m512d v){return _mm512_castsi512_pd(_mm512_and_si512(_mm512_castpd_si512(v),abs_mask));};
      const auto signs=_mm512_setr_pd(-1.,1.,-1.,1.,-1.,1.,-1.,1.);
      alignas(64) double bv[8]={};
      for(int j=0;j<columns;++j){auto v=rhs[(start+j)*n+i];bv[2*j]=v.real();bv[2*j+1]=v.imag();}
      const auto rhsvec=_mm512_load_pd(bv);auto den=absvec(rhsvec);den=_mm512_add_pd(den,_mm512_permute_pd(den,0x55));
      auto accumulate=[&](__m512d z,double ch,double cl){
        const auto vh=_mm512_set1_pd(ch),vl=_mm512_set1_pd(cl);
        const auto product=_mm512_mul_pd(vh,z);
        const auto product_error=_mm512_add_pd(_mm512_fmsub_pd(vh,z,product),_mm512_mul_pd(vl,z));
        // TwoSum has no magnitude-order requirement, including cancellation.
        const auto sum=_mm512_add_pd(hi,product);
        const auto back=_mm512_sub_pd(sum,hi);
        const auto error=_mm512_add_pd(_mm512_sub_pd(hi,_mm512_sub_pd(sum,back)),_mm512_sub_pd(product,back));
        lo=_mm512_add_pd(lo,_mm512_add_pd(error,product_error));hi=sum;
      };
      auto add=[&](int k,cplx value,double scale){
        const double ar=scale*value.real(),ai=scale*value.imag();
        if(!supported(ar)||!supported(ai)||(ar==0.&&scale!=0.&&value.real()!=0.)||(ai==0.&&scale!=0.&&value.imag()!=0.)){
          unsafe=1;return;
        }
        const double er=std::fma(scale,value.real(),-ar),ei=std::fma(scale,value.imag(),-ai);
        const auto z=_mm512_maskz_loadu_pd(mask,reinterpret_cast<const double*>(packed.data()+(size_t)k*nrhs+start));
        accumulate(z,ar,er);
        accumulate(_mm512_mul_pd(_mm512_permute_pd(z,0x55),signs),ai,ei);
        auto az=absvec(z);az=_mm512_add_pd(az,_mm512_permute_pd(az,0x55));
        const double av=std::abs(ar)+std::abs(ai)+std::abs(er)+std::abs(ei);
        den=_mm512_add_pd(den,_mm512_mul_pd(_mm512_set1_pd(av),az));
      };
      for(index_t q=a.rowptr[i];q<a.rowptr[i+1];++q)add(a.colind[q],a.values[q],alpha_);
      if(b){for(index_t q=b->rowptr[i];q<b->rowptr[i+1];++q)add(b->colind[q],b->values[q],beta_);}
      else add(i,cplx(1.,0.),beta_);
      // TwoSum(rhs, -hi), followed by the accumulated low component.
      const auto neg_hi=_mm512_sub_pd(zero,hi),sum=_mm512_add_pd(rhsvec,neg_hi);
      const auto back=_mm512_sub_pd(sum,rhsvec);
      const auto error=_mm512_add_pd(_mm512_sub_pd(rhsvec,_mm512_sub_pd(sum,back)),_mm512_sub_pd(neg_hi,back));
      const auto delta=_mm512_add_pd(sum,_mm512_sub_pd(error,lo));
      alignas(64) double rv[8],dv[8];_mm512_store_pd(rv,delta);_mm512_store_pd(dv,den);
      for(int j=0;j<columns;++j){
        r[(start+j)*n+i]=cplx(rv[2*j],rv[2*j+1]);
        const double eta=(std::abs(rv[2*j])+std::abs(rv[2*j+1]))/std::max(dv[2*j],std::numeric_limits<double>::min());
        if(!std::isfinite(eta))unsafe=1;
        worst=std::max(worst,std::isfinite(eta)?eta:std::numeric_limits<double>::infinity());
      }
    }
    if(!unsafe){if(vectorized)*vectorized=true;return worst;}
#endif
    return residual<long double>(x,nrhs,ldx,rhs,r);
  }

