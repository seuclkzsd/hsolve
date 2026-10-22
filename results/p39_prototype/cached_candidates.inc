// Included inside driver/definite.cpp's anonymous namespace, after its existing
// Lanczos, residual-rescue and selection helpers. No process-global cache.
class P39Threads {
  int old_=0;
public:
  explicit P39Threads(int threads){
#ifdef _OPENMP
    old_=omp_get_max_threads();omp_set_num_threads(threads);
#else
    (void)threads;
#endif
  }
  ~P39Threads(){
#ifdef _OPENMP
    omp_set_num_threads(old_);
#endif
  }
};
bool p39_candidates(const CsrMatrix<cplx>& a,const CsrMatrix<cplx>* b,const SolverConfig& parent,
                    double memory_bytes,DenseMatrix<cplx>& x,std::vector<double>& values,
                    std::vector<double>& hints,std::string& why){
  p39::Cycle cycle;const index_t k=parent.target.k;
  why="no common twisted translation in A/B";
  if(parent.zero_filter_tol>=0||!p39::recognize(a,b,k,cycle))return false;
  const index_t cap=std::min<index_t>(cycle.blocks-1,k+2);
  const double need=64.*a.nrows*(k+cap)+192.*(a.nnz()+(b?b->nnz():0))+1048576.;
  if(!std::isfinite(memory_bytes)||memory_bytes<=need){why="cached partial Bloch workspace budget";return false;}
  const double factor_cap_mb=.8*(memory_bytes-need)/cycle.period/1e6;
  if(factor_cap_mb<1){why="cached partial Bloch factor budget";return false;}
  struct State {
    CsrMatrix<cplx> a,b;
    std::unique_ptr<ShiftedPencil<cplx>> pencil;
    std::unique_ptr<SparseFactorization<cplx>> factor;
    NormEstimate na,nb;BDefiniteness bd;
    Solution<cplx> result;index_t requested=0;
    double shift=0;bool detection_off=false;
  };
  std::vector<State> states(cycle.period);
  struct Pick {double value;index_t mode,column;};std::vector<Pick> picks;
  const double sigma=parent.target.sigma;
  auto calculate=[&](index_t mode,index_t wanted){
    Timer timer;auto& s=states[mode];
    const int threads=cycle.blocks<=4096?1:std::min(std::max(parent.threads,1),4);
    P39Threads thread_scope(threads);
    SolverConfig cfg=parent;cfg.target.k=wanted;cfg.method=Method::ShiftInvertLanczos;
    cfg.certificate=CertificateMode::Off;cfg.inertia_check=Toggle::Off;cfg.certificate_fault_drop=0;
    cfg.tol=std::min(parent.tol*.1,1e-11);cfg.threads=threads;cfg.block_size=0;cfg.ncv=0;
    cfg.max_restarts=std::min<index_t>(parent.max_restarts,100);cfg.seed=parent.seed+mode;
    if(!s.pencil){
      s.a=p39::sector(a,cycle,mode);if(b)s.b=p39::sector(*b,cycle,mode);
      s.pencil=std::make_unique<ShiftedPencil<cplx>>(s.a,b?&s.b:nullptr);
      s.na=estimate_norm2(s.a,30,cfg.seed);
      if(b){s.nb=estimate_norm2(s.b,30,cfg.seed);s.bd=test_b_definiteness(s.b,s.nb);}
      else s.nb.norm2=1.;
      if(!(s.na.norm2>0)||!(s.nb.norm2>0)||!std::isfinite(s.na.norm2)||!std::isfinite(s.nb.norm2))return false;
      if(b&&s.bd.verdict==Definiteness::NotPositive)return false;
    }
    SolveReport report;report.norm2_a=s.na.norm2;report.norm2_b=s.nb.norm2;
    report.problem=b?ProblemType::GeneralizedDefinite:ProblemType::Standard;
    PhaseClock clock;Ctx ctx{cfg,nullptr,report,clock};
    const bool reused=bool(s.factor);FactorStats before;
    if(s.factor)before=s.factor->stats();
    else {
      auto options=factor_options_from(cfg,factor_cap_mb);
      // The same ordering policy as an ordinary inner solve; the model sees the
      // sector's actual sparse pattern and the work of one shifted factorization.
      s.factor=adaptive_analysis(ctx,options,*s.pencil,sigma,plan_work(cfg,report.problem,cycle.blocks,s.na.norm2/s.nb.norm2));
      if(s.factor->estimate().incore_mb>factor_cap_mb){why="sector factors exceed shared cache allowance";return false;}
      s.factor->set_max_memory_mb(factor_cap_mb);
      if(b&&s.bd.verdict==Definiteness::Unknown){
        if(!s.factor->factorize(0.,1.))return false;
        const auto inertia=s.factor->inertia();if(!inertia.valid||inertia.neg||inertia.zero)return false;
      }
      s.shift=factorize_near(ctx,*s.factor,sigma,s.na.norm2/s.nb.norm2,s.detection_off);
    }
    eigen_detail::ShiftInvertShape shape;
    shape.n=cycle.blocks;shape.nev=wanted;shape.factor_entries=s.factor->stats().factor_entries;
    shape.nnz_b=b?s.b.nnz():0;shape.complex_scalars=true;
    const index_t rule=block_size_for(cfg,shape);
    const index_t width=fit_block_size<cplx>(ctx,cycle.blocks,wanted,0,4*wanted,rule,std::min(rule,reserved_block_size(cfg)));
    DefiniteRun<cplx> run;
    s.result=Solution<cplx>{};
    lanczos_run(ctx,*s.factor,*s.pencil,s.shift,Which::LargestMagnitude,wanted,width,
                static_cast<const DenseMatrix<cplx>*>(nullptr),run,0,true);
    std::vector<PairMetrics> metrics;
    verify_and_rescue(ctx,*s.factor,*s.pencil,run.all,metrics,s.na.norm2,s.nb.norm2,[]{});
    bool accepted=run.all.size()>=wanted;
    for(const auto& metric:metrics)accepted=accepted&&std::isfinite(metric.backward_error)&&metric.backward_error<=cfg.tol;
    index_t dropped=0;auto selected=take_columns(run.all,select_nearest(run.all.lambda,sigma,wanted,-1.,dropped));
    accepted=accepted&&selected.size()==wanted;
    for(double value:selected.lambda)accepted=accepted&&std::isfinite(value);
    s.result.eigenvalues=std::move(selected.lambda);s.result.eigenvectors=std::move(selected.x);
    s.result.report.success=accepted;s.requested=wanted;
    const auto& after=s.factor->stats();
    std::fprintf(stderr,"P39 sector mode=%lld period=%lld n=%lld requested=%lld pairs=%zu success=%d reused=%d analyses=%lld factors=%lld rhs=%lld shift=%.17g seconds=%.9g\n",
      (long long)mode,(long long)cycle.period,(long long)cycle.blocks,(long long)wanted,s.result.eigenvalues.size(),int(accepted),int(reused),
      (long long)(after.analyses-before.analyses),(long long)(after.factorizations-before.factorizations),(long long)(after.rhs_solved-before.rhs_solved),s.shift,timer.seconds());
#if P39_SECTOR_MODE == 1
    s.factor.reset();
#endif
    return accepted;
  };
  try {
    for(index_t mode=0;mode<cycle.period;++mode)if(!calculate(mode,std::min<index_t>(2,cap))){why="cached sector preliminary solve failed: "+why;return false;}
    while(true){
      picks.clear();
      for(index_t mode=0;mode<cycle.period;++mode){const auto& w=states[mode].result.eigenvalues;
        for(index_t j=0;j<static_cast<index_t>(w.size());++j)picks.push_back({w[j],mode,j});}
      std::stable_sort(picks.begin(),picks.end(),[&](const Pick& l,const Pick& r){return std::abs(l.value-sigma)<std::abs(r.value-sigma);});
      const double radius=picks.size()>=static_cast<std::size_t>(k)?std::abs(picks[k-1].value-sigma):std::numeric_limits<double>::infinity();
      const double margin=64*std::numeric_limits<double>::epsilon()*std::max(std::abs(sigma),radius);
      bool expanded=false;
      for(index_t mode=0;mode<cycle.period;++mode){auto& s=states[mode];if(s.requested>=cap)continue;
        double tail=0;for(double v:s.result.eigenvalues)tail=std::max(tail,std::abs(v-sigma));
        if(picks.size()<static_cast<std::size_t>(k)||tail<=radius+margin){
          if(!calculate(mode,std::min(cap,2*s.requested))){why="cached sector expansion failed";return false;}
          expanded=true;
        }
      }
      if(!expanded)break;
    }
  } catch(const Error& error){
    if(error.code()==Error::Code::Internal||error.code()==Error::Code::Io)throw;
    why=std::string("cached sector rejected: ")+error.what();return false;
  }
  if(picks.size()<static_cast<std::size_t>(k)){why="not enough cached sector candidates";return false;}
  // Free all factors before allocating the lifted output and before outer counts.
  for(auto& state:states)state.factor.reset();
  x=DenseMatrix<cplx>(a.nrows,k);values.resize(k);hints.clear();
  for(const auto& pick:picks)hints.push_back(pick.value);
  for(index_t j=0;j<k;++j){const auto& pick=picks[j];values[j]=pick.value;
    const double theta=(cycle.phase+2*std::acos(-1.)*pick.mode)/cycle.period;
    for(index_t t=0;t<cycle.period;++t){const cplx weight=std::polar(1/std::sqrt(double(cycle.period)),theta*t);
      for(index_t g=0;g<cycle.blocks;++g)x(g*cycle.period+t,j)=weight*states[pick.mode].result.eigenvectors(g,pick.column);}
  }
  why="verified partial Bloch candidates; direct Lanczos; factor reuse="+std::to_string(P39_SECTOR_MODE==2);
  return true;
}
