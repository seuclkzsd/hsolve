#if P37_SCALAR_RESIDUAL
    const auto& a=pencil_.a();const auto* b=pencil_.b();const int n=order();double worst=0;
    r.resize((size_t)n*nrhs);
#pragma omp parallel for collapse(2) schedule(static) reduction(max:worst)
    for(index_t col=0;col<nrhs;++col)for(int i=0;i<n;++i){
      R sr=0,si=0;auto v=rhs[col*n+i];R den=std::abs(R(v.real()))+std::abs(R(v.imag()));
      auto add=[&](int k,R ar,R ai){
        auto z=x[col*ldx+k];R zr=z.real(),zi=z.imag();
        sr+=ar*zr-ai*zi;si+=ar*zi+ai*zr;
        den+=(std::abs(ar)+std::abs(ai))*(std::abs(zr)+std::abs(zi));
      };
      for(index_t q=a.rowptr[i];q<a.rowptr[i+1];++q){auto z=a.values[q];add(a.colind[q],R(alpha_)*R(z.real()),R(alpha_)*R(z.imag()));}
      if(b){for(index_t q=b->rowptr[i];q<b->rowptr[i+1];++q){auto z=b->values[q];add(b->colind[q],R(beta_)*R(z.real()),R(beta_)*R(z.imag()));}}
      else add(i,R(beta_),R(0));
      R dr=R(v.real())-sr,di=R(v.imag())-si;r[col*n+i]=cplx(double(dr),double(di));
      double eta=double((std::abs(dr)+std::abs(di))/std::max(den,std::numeric_limits<R>::min()));
      worst=std::max(worst,std::isfinite(eta)?eta:std::numeric_limits<double>::infinity());
    }
    return worst;
#else
