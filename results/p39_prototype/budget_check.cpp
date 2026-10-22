#include "/tmp/os2026-p39/definite.cpp"
#include <fstream>
#include <iostream>
#include <nlohmann/json.hpp>
#include "hsolve/io.hpp"
using json=nlohmann::json;
hs::CsrMatrix<hs::cplx> cm(hs::LoadedMatrix loaded){
 if(loaded.is_complex())return std::get<hs::CsrMatrix<hs::cplx>>(std::move(loaded.matrix));
 return hs::to_complex(std::get<hs::CsrMatrix<double>>(std::move(loaded.matrix)));
}
int main(){
 const std::string base="/tmp/os2026-p38/data/cases/cycle-ghep/";
 auto a=cm(hs::load_matrix(base+"A.npz")),b=cm(hs::load_matrix(base+"B.npz"));
 std::ifstream in(base+"config.json");std::string raw((std::istreambuf_iterator<char>(in)),{});
 auto cfg=hs::parse_config(raw);cfg.threads=8;cfg.memory_budget_gb=12;
#ifdef _OPENMP
 omp_set_num_threads(4);
#endif
 json rows=json::array();
 for(auto item:std::vector<std::pair<std::string,double>>{{"zero",0.},{"nan",std::numeric_limits<double>::quiet_NaN()},{"small",2.*1048576.},{"success",128.*1048576.}}){
  hs::DenseMatrix<hs::cplx> x;std::vector<double> w,h;std::string why;
  bool accepted=hs::driver::p39_candidates(a,&b,cfg,item.second,x,w,h,why);
  int threads=4;
#ifdef _OPENMP
  threads=omp_get_max_threads();
#endif
  if(threads!=4||accepted!=(item.first=="success"))throw std::runtime_error("P39 budget/thread contract failed: "+item.first+" "+why);
  rows.push_back(json{{"profile",item.first},{"accepted",accepted},{"threads_after",threads},{"why",why},{"pairs",w.size()}});
  if(accepted){hs::write_npy_vector("/tmp/os2026-p39/budget-eigenvalues.npy",w);hs::write_npy_matrix("/tmp/os2026-p39/budget-eigenvectors.npy",x);}
 }
 std::cout<<rows.dump(2)<<std::endl;
}
