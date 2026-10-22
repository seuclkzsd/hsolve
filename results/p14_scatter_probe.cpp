// Exercise the actual GNU Fortran MUMPS 5.8.2 scatter routine using valid front
// metadata. Run on the cluster with a MUMPS install's lib directory as argv[1].
// Checks every output entry and padding against an independent permutation.
#include <dlfcn.h>
#include <omp.h>

#include <array>
#include <complex>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>

template <class T, class R>
void check(const std::string& dir, char kind) {
  const std::string name(1, kind);
  void* lib = dlopen((dir + "/lib" + name + "mumps_seq.so").c_str(), RTLD_NOW | RTLD_LOCAL);
  if (!lib) throw std::runtime_error(dlerror());
  using Scatter = void (*)(int*, int*, int*, int*, int*, R*, int*, T*, int*, int*, int*,
                           T*, int*, int*, int*, int*, int*, int*, long long*, int*, int*,
                           int*, int*, int*, int*);
  const auto scatter = reinterpret_cast<Scatter>(dlsym(lib, (name + "mumps_scatter_rhs_").c_str()));
  if (!scatter) throw std::runtime_error(dlerror());
  int checked = 0;
  for (int threads : {1, 2, 8}) {
    omp_set_num_threads(threads);
    for (int round = 0; round < 48; ++round) {
      int n = round % 6 == 0 ? 32767 : (round % 6 == 1 ? 32768 : 65537);
      int nodes = round % 6 == 2 ? 63 : (round % 6 == 3 ? 64 : 129);
      int nrhs = std::array<int, 3>{1, 2, 9}[round % 3];
      int cols = nrhs + 1, ldrhs = n + 3, ldout = n + 7;
      int mtype = round % 2, scaled = (round / 2) % 2;
      int slaves = 1, myid = 0, comm = -987654, nbfs = n;
      std::array<int, 500> keep{};
      std::array<long long, 150> keep8{};
      std::array<int, 60> icntl{};
      std::array<int, 80> info{};
      const int ixsz = (round / 4) % 2 ? 2 : 0;
      keep[27] = nodes;
      keep[45] = 1;
      keep[49] = (round / 8) % 2 ? 2 : 0;
      keep[88] = n;
      keep[198] = 1;
      keep[221] = ixsz;
      keep[349] = (round / 16) % 2 ? 2 : 0;
      keep[15] = sizeof(T);
      keep[362] = 1024;
      keep[363] = 512;
      std::vector<int> ptr(nodes), proc(nodes, 0), step(n, 1), pos(n), selected(n);
      std::vector<int> iw(2 * n + (12 + ixsz) * nodes, 1);
      const bool transpose = mtype != 1 && keep[49] == 0;
      int at = 1, offset = 0;
      for (int f = 0; f < nodes; ++f) {
        // Empty interior fronts exercise delayed/zero-pivot front handling.
        const int piv = f == nodes - 1 ? n - offset : (f % 11 == 3 ? 0 : n / nodes);
        ptr[f] = at;
        iw[at + ixsz - 1] = 0;
        iw[at + 3 + ixsz - 1] = piv;
        iw[at + 5 + ixsz - 1] = 0;
        const int first = at + 6 + ixsz;
        for (int j = 0; j < piv; ++j) {
          const int local = offset + j;
          const int row = (local + round * 17) % n;
          const int col = (n - 1 - local + round * 13) % n;
          iw[first - 1 + j] = row + 1;
          iw[first - 1 + piv + j] = col + 1;
          const int source = transpose ? col : row;
          pos[source] = local + 1;
          selected[local] = source;
        }
        offset += piv;
        at += 2 * piv + 12 + ixsz;
      }
      // Both root encodings use the same row/column layout as the other fronts.
      if (round % 3 != 0) {
        keep[round % 3 == 1 ? 37 : 19] = n;
        step[n - 1] = nodes;
      }
      int liw = static_cast<int>(iw.size());
      const T sentinel = T(-12345);
      std::vector<T> rhs(ldrhs * cols, sentinel), out(ldout * cols, sentinel);
      std::vector<T> expected(out);
      std::vector<R> scaling(n);
      for (int i = 0; i < n; ++i) scaling[i] = R(1 << (i % 4)) / R(8);
      for (int k = 0; k < nrhs; ++k) {
        for (int i = 0; i < n; ++i) {
          const R real = R((i * 13 + k * 97) % 2048 - 1024) / R(16);
          if constexpr (std::is_same_v<T, R>) rhs[i + k * ldrhs] = real;
          else rhs[i + k * ldrhs] = T(real, R((i * 7 + k) % 128 - 64) / R(32));
        }
        for (int i = 0; i < n; ++i) {
          const T value = rhs[selected[i] + k * ldrhs];
          expected[i + k * ldout] = scaled ? value * scaling[i] : value;
        }
      }
      scatter(&slaves, &n, &myid, &comm, &scaled, scaling.data(), &mtype, rhs.data(),
              &ldrhs, &cols, &nrhs, out.data(), &ldout, &cols, pos.data(), &nbfs,
              ptr.data(), keep.data(), keep8.data(), proc.data(), iw.data(), &liw,
              step.data(), icntl.data(), info.data());
      if (info[0] < 0 || std::memcmp(out.data(), expected.data(), out.size() * sizeof(T)))
        throw std::runtime_error(name + " scatter mismatch: threads=" + std::to_string(threads) +
                                 " round=" + std::to_string(round));
      ++checked;
    }
  }
  std::cout << name << ": " << checked << " scatter cases passed (bitwise, including padding)\n";
  dlclose(lib);
}

template <class T, class R>
void check_gather(const std::string& dir, char kind) {
  const std::string name(1, kind);
  void* lib = dlopen((dir + "/lib" + name + "mumps_seq.so").c_str(), RTLD_NOW | RTLD_LOCAL);
  if (!lib) throw std::runtime_error(dlerror());
  using Gather = void (*)(int*, int*, int*, int*, int*, int*, T*, int*, int*, int*, int*,
                          int*, long long*, int*, int*, int*, int*, int*, int*, int*, T*, int*,
                          int*, R*, int*, T*, int*, int*, int*, int*, int*, int*);
  const auto gather = reinterpret_cast<Gather>(dlsym(lib, (name + "mumps_gather_solution_").c_str()));
  if (!gather) throw std::runtime_error(dlerror());
  int checked = 0;
  for (int threads : {1, 2, 8}) {
    omp_set_num_threads(threads);
    for (int round = 0; round < 48; ++round) {
      int n = std::array<int, 3>{32767, 32768, 65537}[round % 3];
      int nrhs = std::array<int, 3>{1, 2, 9}[(round / 3) % 3];
      int cols = nrhs + 3, ldrhs = n + 3, ldinternal = n + 7;
      int mtype = round % 2, scaled = (round / 2) % 2;
      int slaves = 1, myid = 0, comm = -987654, jbeg = 2;
      std::array<int, 500> keep{};
      std::array<long long, 150> keep8{};
      keep[45] = 1;
      keep[241] = (round / 4) % 2;
      keep[349] = (round / 8) % 2 ? 2 : 0;
      keep[361] = threads;
      keep[362] = 1024;
      std::vector<int> pos(n), perm(cols);
      const T sentinel = T(-12345);
      std::vector<T> rhs(ldrhs * cols, sentinel), internal(ldinternal * cols, sentinel);
      std::vector<T> expected(rhs);
      std::vector<R> scaling(n);
      for (int j = 0; j < cols; ++j) perm[j] = cols - j;
      for (int i = 0; i < n; ++i) {
        pos[i] = i % 11 == 0 ? -1 : (i % 7 == 0 ? 0 : (i + round * 17) % n + 1);
        scaling[i] = R(1 << (i % 4)) / R(8);
      }
      for (int j = 0; j < nrhs; ++j) {
        for (int i = 0; i < n; ++i) {
          const R real = R((i * 13 + j * 97) % 2048 - 1024) / R(16);
          if constexpr (std::is_same_v<T, R>) internal[i + j * ldinternal] = real;
          else internal[i + j * ldinternal] = T(real, R((i * 7 + j) % 128 - 64) / R(32));
        }
        const int dest = keep[241] ? perm[j + jbeg - 1] - 1 : j + jbeg - 1;
        for (int i = 0; i < n; ++i) {
          T value = T(0);
          if (pos[i] > 0) {
            value = internal[pos[i] - 1 + j * ldinternal];
            if (scaled) value *= scaling[pos[i] - 1];
          }
          expected[i + dest * ldrhs] = value;
        }
      }
      // The existing single-process branch never inspects distributed metadata.
      int dummy = 0, one = 1, bytes = sizeof(int);
      T work{};
      gather(&slaves, &n, &myid, &comm, &nrhs, &mtype, rhs.data(), &ldrhs, &cols, &jbeg,
             &dummy, keep.data(), keep8.data(), &dummy, &dummy, &one, &dummy, &dummy,
             &one, &bytes, &work, &one, &scaled, scaling.data(), &n, internal.data(),
             &ldinternal, &cols, pos.data(), &n, perm.data(), &cols);
      if (std::memcmp(rhs.data(), expected.data(), rhs.size() * sizeof(T)))
        throw std::runtime_error(name + " gather mismatch: threads=" + std::to_string(threads) +
                                 " round=" + std::to_string(round));
      ++checked;
    }
  }
  std::cout << name << ": " << checked << " gather cases passed (bitwise, including padding)\n";
  dlclose(lib);
}

int main(int argc, char** argv) {
  if (argc != 2) return 2;
  try {
    omp_set_dynamic(0);
    check<float, float>(argv[1], 's');
    check<double, double>(argv[1], 'd');
    check<std::complex<float>, float>(argv[1], 'c');
    check<std::complex<double>, double>(argv[1], 'z');
    check_gather<float, float>(argv[1], 's');
    check_gather<double, double>(argv[1], 'd');
    check_gather<std::complex<float>, float>(argv[1], 'c');
    check_gather<std::complex<double>, double>(argv[1], 'z');
  } catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
