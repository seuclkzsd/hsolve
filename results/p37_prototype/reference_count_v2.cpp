#include <fstream>
#include <iostream>
#include <nlohmann/json.hpp>
#include "hsolve/factor.hpp"
#include "hsolve/io.hpp"
using json=nlohmann::json;
template<class T> void count(const hs::CsrMatrix<T>& a,const hs::CsrMatrix<T>* b,const json& item){
  hs::ShiftedPencil<T> pencil(a,b);
  for(int ordering:{3,7}){
    hs::FactorOptions options;options.threads=8;options.ordering=ordering;options.max_memory_mb=4096;
    hs::InertiaCounter<T> counter(pencil,{},options);
    auto lo=counter.count(1.,-item.at("lower").get<double>());
    auto hi=counter.count(1.,-item.at("upper").get<double>());
    std::cout<<json{{"case",item.at("case")},{"ordering",ordering},{"lower_valid",lo.valid},{"upper_valid",hi.valid},{"lower_negative",lo.neg},{"upper_negative",hi.neg},{"window_count",hi.neg-lo.neg},{"analyses",counter.stats().analyses},{"counts",counter.stats().counts},{"count_s",counter.stats().count_s},{"estimate_mb",counter.estimate().incore_mb}}.dump()<<std::endl;
  }
}
hs::CsrMatrix<hs::cplx> complex_matrix(hs::LoadedMatrix loaded) {
  if(loaded.is_complex()) return std::get<hs::CsrMatrix<hs::cplx>>(std::move(loaded.matrix));
  return hs::to_complex(std::get<hs::CsrMatrix<double>>(std::move(loaded.matrix)));
}
int main(int argc,char** argv){
  if(argc!=2) return 2;
  json manifest;std::ifstream in(argv[1]);in>>manifest;
  for(const auto& item:manifest){
    auto a=complex_matrix(hs::load_matrix(item.at("a").get<std::string>()));
    std::unique_ptr<hs::CsrMatrix<hs::cplx>> b;
    if(item.contains("b")) b=std::make_unique<hs::CsrMatrix<hs::cplx>>(complex_matrix(hs::load_matrix(item.at("b").get<std::string>())));
    count(a,b.get(),item);
  }
}
