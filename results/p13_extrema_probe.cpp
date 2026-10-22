// P13 regression probe for the pinned GNU Fortran MUMPS 5.8.2 extrema routine.
// Compile/run on the cluster; pass the tested MUMPS install's lib directory.
// Exercises the actual library routine concurrently, including null-only input,
// repeated values, subnormals, infinities, and resetting statistics between runs.
#include <dlfcn.h>
#include <omp.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

template <class T>
void check(const std::string& dir, char kind) {
  const std::string name(1, kind);
  void* lib = dlopen((dir + "/lib" + name + "mumps_seq.so").c_str(), RTLD_NOW | RTLD_LOCAL);
  if (!lib) throw std::runtime_error(dlerror());
  using Update = void (*)(const T*, T*, const int*, const int*);
  const auto update = reinterpret_cast<Update>(dlsym(
      lib, ("__" + name + "mumps_fac_front_aux_m_MOD_" + name + "mumps_update_minmax_pivot").c_str()));
  if (!update) throw std::runtime_error(dlerror());
  constexpr int n = 65536;
  std::vector<T> values(n);
  std::vector<int> nulls(n);
  int checked = 0;
  for (const int threads : {1, 2, 8}) {
    for (int round = 0; round < 12; ++round) {
      const int mode = round % 6;
      for (int i = 0; i < n; ++i) {
        values[i] = T(1 + ((i * 8191 + round * 97) % n));
        nulls[i] = mode == 2 || (mode != 0 && (i + round) % 13 == 0);
        if (mode == 3) values[i] *= std::numeric_limits<T>::denorm_min();
        if (mode == 5) values[i] = T(7);  // ties on every thread
      }
      if (mode == 1) { values[17] = T(0); nulls[17] = 1; }
      if (mode == 4) values[n / 2] = std::numeric_limits<T>::infinity();
      const T huge = std::numeric_limits<T>::max();
      std::array<T, 3> expected{huge, huge, T(0)};
      for (int i = 0; i < n; ++i) {
        expected[0] = std::min(expected[0], values[i]);
        if (!nulls[i]) expected[1] = std::min(expected[1], values[i]);
        expected[2] = std::max(expected[2], values[i]);
      }
      alignas(64) std::array<T, 230> stats{};
      std::array<int, 500> keep{};
      stats[18] = stats[19] = huge;
      keep[404] = threads == 1 ? 0 : 1;
#pragma omp parallel for schedule(static, 1) num_threads(threads)
      for (int i = 0; i < n; ++i) update(&values[i], stats.data(), keep.data(), &nulls[i]);
      for (int i = 0; i < 3; ++i) {
        if (stats[18 + i] != expected[i])
          throw std::runtime_error(name + ": incorrect extrema, threads=" + std::to_string(threads) +
                                   " round=" + std::to_string(round) + " statistic=" + std::to_string(i));
      }
      ++checked;
    }
  }
  std::cout << name << ": " << checked << " parallel/serial cases passed\n";
  dlclose(lib);
}

int main(int argc, char** argv) {
  if (argc != 2) return 2;
  try {
    omp_set_dynamic(0);
    check<float>(argv[1], 's');
    check<double>(argv[1], 'd');
    check<float>(argv[1], 'c');
    check<double>(argv[1], 'z');
  } catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
