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
int main(int argc,char** argv){
  if(argc!=2)return 2;json manifest;std::ifstream in(argv[1]);in>>manifest;
  for(const auto& item:manifest){
    auto a=hs::load_matrix(item.at("a").get<std::string>());
    if(a.is_complex())throw std::runtime_error("This independent check expects the two real photonic pencils");
    std::unique_ptr<hs::CsrMatrix<double>> b;
    if(item.contains("b")){auto loaded=hs::load_matrix(item.at("b").get<std::string>());if(loaded.is_complex())throw std::runtime_error("complex B");b=std::make_unique<hs::CsrMatrix<double>>(std::get<hs::CsrMatrix<double>>(std::move(loaded.matrix)));}
    count(std::get<hs::CsrMatrix<double>>(a.matrix),b.get(),item);
  }
}
