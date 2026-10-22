#include <fstream>
#include <iostream>
#include <nlohmann/json.hpp>
#include "hsolve/io.hpp"
#include "band_backend.hpp"
using json=nlohmann::json;
hs::CsrMatrix<hs::cplx> load(const std::string& path){
  auto m=hs::load_matrix(path);
  return m.is_complex()?std::get<hs::CsrMatrix<hs::cplx>>(std::move(m.matrix)):hs::to_complex(std::get<hs::CsrMatrix<double>>(std::move(m.matrix)));
}
int main(int argc,char** argv){
  if(argc!=2)return 2;
  json manifest;std::ifstream in(argv[1]);in>>manifest;int failures=0;
  for(const auto& item:manifest){
    try{
      auto a=load(item.at("a"));std::unique_ptr<hs::CsrMatrix<hs::cplx>> b;
      if(item.contains("b"))b=std::make_unique<hs::CsrMatrix<hs::cplx>>(load(item.at("b")));
      hs::ShiftedPencil<hs::cplx> pencil(a,b.get());const int n=a.nrows;
      auto original_rhs=hs::npy_to_vector<hs::cplx>(hs::read_npy(item.at("rhs").get<std::string>()));
      for(const std::string profile:{"normal","small_x","large_x","small_pencil","large_pencil","zero","infinity","nan"}){
        double alpha=item.value("alpha",1.),beta=item.value("beta",0.),scale=1.;
        if(profile=="small_x")scale=1e-120;
        if(profile=="large_x")scale=1e120;
        if(profile=="small_pencil"){alpha*=1e-120;beta*=1e-120;}
        if(profile=="large_pencil"){alpha*=1e120;beta*=1e120;}
        if(profile=="zero"){alpha=beta=0.;}
        hs::FactorOptions options;options.threads=8;options.max_memory_mb=1000;
        auto f=hs::p33::try_make(pencil,options,0);if(!f)throw std::runtime_error("structural rejection");
        f->set_null_pivot_detection(false);f->factorize(alpha,beta);
        auto* backend=dynamic_cast<hs::p33::Backend*>(f.get());
        for(int nrhs:{1,3,4,5,8}){
          hs::DenseMatrix<hs::cplx> x(n,nrhs),rhs(n,nrhs);
          for(int j=0;j<nrhs;++j)for(int i=0;i<n;++i){rhs(i,j)=original_rhs[j*n+i];x(i,j)=rhs(i,j)*scale;}
          if(profile=="infinity")x(0,0)=hs::cplx(std::numeric_limits<double>::infinity(),0.);
          if(profile=="nan")x(0,0)=hs::cplx(std::numeric_limits<double>::quiet_NaN(),0.);
          std::vector<hs::cplx> rhs_vector(rhs.data(),rhs.data()+size_t(n)*nrhs),residual;bool vectorized=false;
          double eta=backend->diagnostic_correction(x.data(),nrhs,n,rhs_vector,residual,vectorized);
          const bool expected=profile=="normal"||profile=="zero";
          if(vectorized!=expected)throw std::runtime_error("unexpected vector/fallback decision: "+profile);
          const bool nonfinite=profile=="infinity"||profile=="nan";
          if(nonfinite&&std::isfinite(eta))throw std::runtime_error("nonfinite residual accepted");
          const std::string prefix=item.at("prefix").get<std::string>()+"-"+profile+"-"+std::to_string(nrhs);
          hs::DenseMatrix<hs::cplx> r(n,nrhs);std::copy(residual.begin(),residual.end(),r.data());
          hs::write_npy_matrix(prefix+"-x.npy",x);hs::write_npy_matrix(prefix+"-rhs.npy",rhs);hs::write_npy_matrix(prefix+"-r.npy",r);
          std::cout<<json{{"id",item.at("id")},{"profile",profile},{"nrhs",nrhs},{"alpha",alpha},{"beta",beta},{"prefix",prefix},{"vectorized",vectorized},{"nonfinite",nonfinite},{"eta",std::isfinite(eta)?json(eta):json(nullptr)},{"valid",true}}.dump()<<std::endl;
        }
      }
    }catch(const std::exception& e){++failures;std::cout<<json{{"id",item.at("id")},{"valid",false},{"error",e.what()}}.dump()<<std::endl;}
  }
  return failures?1:0;
}
