#include <fstream>
#include <iostream>
#include <nlohmann/json.hpp>
#include "hsolve/io.hpp"
#include "band_backend_reuse.hpp"
using json=nlohmann::json;
hs::CsrMatrix<hs::cplx> load(const std::string& file){auto m=hs::load_matrix(file);if(m.is_complex())return std::get<hs::CsrMatrix<hs::cplx>>(std::move(m.matrix));return hs::to_complex(std::get<hs::CsrMatrix<double>>(std::move(m.matrix)));}
int main(int argc,char** argv){
 if(argc!=2)return 2;std::ifstream in(argv[1]);json manifest;in>>manifest;int failures=0;
 for(auto& item:manifest){try{
  auto a=load(item.at("a"));std::unique_ptr<hs::CsrMatrix<hs::cplx>> b; if(item.contains("b"))b=std::make_unique<hs::CsrMatrix<hs::cplx>>(load(item.at("b"))); hs::ShiftedPencil<hs::cplx> pencil(a,b.get()); double alpha=item.value("alpha",1.), beta=item.value("beta",0.);hs::FactorOptions options;options.threads=8;options.max_memory_mb=1000;
  auto f=hs::p33::try_make(pencil,options,0);if(!f)throw std::runtime_error("unexpected structural rejection");
  bool initial=f->factorize(alpha,beta);auto first=f->inertia();auto initial_nulls=f->stats().null_pivots;bool singular=item.value("singular",false);
  json row={{"id",item.at("id")},{"initial_valid",initial},{"initial_negative",first.neg},{"singular",singular},{"initial_null_pivots",initial_nulls}};
  if(item.contains("expected_null_pivots")&&initial_nulls!=item.at("expected_null_pivots").get<int>())throw std::runtime_error("null-pivot multiplicity contract mismatch");
  if(!initial){std::vector<hs::cplx> probe(a.nrows,hs::cplx(1,0));bool rejected=false;try{f->solve(probe.data(),1,a.nrows);}catch(...){rejected=true;}if(!rejected)throw std::runtime_error("failed factors became available before checked activation");}
  if(singular){if(initial)throw std::runtime_error("rank-deficient matrix accepted");std::cout<<row.dump()<<std::endl;continue;}
  if(!initial){f->set_null_pivot_detection(false);if(!f->factorize(alpha,beta))throw std::runtime_error("nonsingular factor rejected with detection off");}
  if(f->inertia().neg!=item.at("negative").get<int>())throw std::runtime_error("inertia mismatch");
  auto rhs=hs::npy_to_vector<hs::cplx>(hs::read_npy(item.at("rhs").get<std::string>()));int n=a.nrows;json solves=json::array();
  for(int nrhs:{1,3,4,5,8}){int ld=n+3;std::vector<hs::cplx> x((size_t)ld*nrhs,hs::cplx(17,19));for(int j=0;j<nrhs;++j)std::copy_n(rhs.data()+j*n,n,x.data()+j*ld);
   f->solve(x.data(),nrhs,ld);hs::DenseMatrix<hs::cplx> result(n,nrhs);for(int j=0;j<nrhs;++j){std::copy_n(x.data()+j*ld,n,result.col(j));for(int i=n;i<ld;++i)if(x[j*ld+i]!=hs::cplx(17,19))throw std::runtime_error("RHS padding overwritten");}
   std::string dest=item.at("prefix").get<std::string>()+"-"+std::to_string(nrhs)+".npy";hs::write_npy_matrix(dest,result);solves.push_back(dest);
  }
  f->set_null_pivot_detection(true);auto counted=f->count(alpha,beta);row["count_valid"]=counted.valid;row["count_negative"]=counted.neg;
  if(counted.valid&&counted.neg!=item.at("negative").get<int>())throw std::runtime_error("count mismatch");
  if(f->inertia().valid)throw std::runtime_error("count retained solve validity");
  bool threw=false;try{f->solve(rhs.data(),1,n);}catch(...){threw=true;}if(!threw)throw std::runtime_error("solve after count did not reject");
  row["solves"]=solves;row["analyses"]=f->stats().analyses;row["valid"]=true;std::cout<<row.dump()<<std::endl;
 }catch(const std::exception& e){++failures;std::cout<<json{{"id",item.at("id")},{"valid",false},{"error",e.what()}}.dump()<<std::endl;}}
 return failures?1:0;
}
