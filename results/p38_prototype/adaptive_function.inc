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
