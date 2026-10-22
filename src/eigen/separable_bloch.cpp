// Matrix-verified Bloch curl-curl candidates. The forward difference has symbol
// d_j = sqrt(alpha_j) * (exp(i theta_j) - 1); each Fourier block is
// ||d||^2 I - d d^H. Its transverse space supplies candidates, not a certificate.
#include "eigen/separable_curl.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <complex>
#include <limits>
#include <string>
#include <utility>
#include <vector>

namespace hs::eigen_detail {
namespace {
bool finite(cplx z) { return std::isfinite(z.real()) && std::isfinite(z.imag()); }

struct BlochModel {
  std::array<index_t, 3> cells{}, stride{};
  std::array<double, 3> mass{}, alpha{}, phase{};
  std::array<cplx, 3> wrap{};
  index_t volume = 0;
  index_t index(int d, const std::array<index_t, 3>& p) const {
    return d * volume + p[0] * stride[0] + p[1] * stride[1] + p[2];
  }
};

bool recognize(const CsrMatrix<cplx>& a, const CsrMatrix<cplx>* b, BlochModel& m,
               std::string& why) {
  const index_t n = a.nrows;
  why = "periodic first row";
  if (n < 81 || n % 3 || a.rowptr[1] != 13 || a.colind[0] != 0 || a.colind[1] != 1)
    return false;
  m.volume = n / 3;
  // Row zero of the x block: diagonal, +/-z, +/-y, then four entries in each other block.
  const index_t nz = a.colind[3], span_y = a.colind[4];
  if (nz < 3 || a.colind[2] != nz - 1 || span_y % nz || a.colind[5] < m.volume)
    return false;
  const index_t ny = span_y / nz + 1;
  if (ny < 3 || ny > m.volume / nz || m.volume % (ny * nz)) return false;
  const index_t nx = m.volume / (ny * nz);
  if (nx < 3) return false;
  m.cells = {nx, ny, nz};
  m.stride = {ny * nz, nz, 1};
  why = "periodic block-constant diagonal mass";
  if (b && (b->nrows != n || b->nnz() != n)) return false;
  for (int d = 0; d < 3; ++d) {
    const cplx mass = b ? b->values[d * m.volume] : cplx{1};
    if (!finite(mass) || mass.imag() != 0 || mass.real() <= 0) return false;
    m.mass[d] = mass.real();
    if (b)
      for (index_t row = d * m.volume; row < (d + 1) * m.volume; ++row)
        if (b->rowptr[row] != row || b->rowptr[row + 1] != row + 1 ||
            b->colind[row] != row || b->values[row] != mass)
          return false;
  }
  auto at = [&](index_t row, index_t col) {
    const auto begin = a.colind.begin() + a.rowptr[row], end = a.colind.begin() + a.rowptr[row + 1];
    const auto it = std::lower_bound(begin, end, col);
    return it == end || *it != col ? cplx{} : a.values[it - a.colind.begin()];
  };
  why = "periodic positive coefficients and unit phases";
  for (int d = 0; d < 3; ++d) {
    const int block = d == 0 ? 1 : 0;
    const index_t row = block * m.volume;
    m.alpha[d] = -at(row, row + m.stride[d]).real() / m.mass[block];
    if (!std::isfinite(m.alpha[d]) || m.alpha[d] <= 0) return false;
    const cplx wrap = std::conj(-at(row, row + (m.cells[d] - 1) * m.stride[d]) /
                              (m.alpha[d] * m.mass[block]));
    if (!finite(wrap) || std::abs(std::abs(wrap) - 1) > 128 * std::numeric_limits<double>::epsilon())
      return false;
    m.wrap[d] = wrap / std::abs(wrap);
    m.phase[d] = std::arg(m.wrap[d]);
  }
  std::array<double, 3> diagonal{};
  std::array<std::array<double, 3>, 3> cross{};
  double largest = 0;
  for (int d = 0; d < 3; ++d) {
    for (int e = 0; e < 3; ++e) {
      if (d == e) continue;
      diagonal[d] += 2 * m.alpha[e] * m.mass[d];
      cross[d][e] = -static_cast<double>(std::sqrt(
          static_cast<long double>(m.alpha[d]) * m.alpha[e] * m.mass[d] * m.mass[e]));
      if (!std::isfinite(cross[d][e])) return false;
      largest = std::max(largest, std::abs(cross[d][e]));
    }
    if (!std::isfinite(diagonal[d])) return false;
    largest = std::max(largest, diagonal[d]);
  }
  const double threshold = 128 * std::numeric_limits<double>::epsilon() * largest;
  bool match = true;
#pragma omp parallel for reduction(&& : match) schedule(static)
  for (index_t row = 0; row < n; ++row) {
    const int d = static_cast<int>(row / m.volume);
    const index_t local = row % m.volume;
    const std::array<index_t, 3> pos{local / m.stride[0], local / nz % ny, local % nz};
    std::array<std::pair<index_t, cplx>, 13> expected{};
    int count = 0;
    expected[count++] = {row, diagonal[d]};
    for (int e = 0; e < 3; ++e) {
      if (d == e) continue;
      for (int sign : {-1, 1}) {
        auto p = pos;
        p[e] += sign;
        cplx phase = 1;
        if (p[e] < 0) {
          p[e] += m.cells[e];
          phase = std::conj(m.wrap[e]);
        } else if (p[e] == m.cells[e]) {
          p[e] = 0;
          phase = m.wrap[e];
        }
        expected[count++] = {m.index(d, p), -m.alpha[e] * m.mass[d] * phase};
      }
      // Off-diagonal block is -sqrt(alpha_d alpha_e mass_d mass_e) D_e^H D_d.
      for (int u : {0, 1})
        for (int v : {0, 1}) {
          auto p = pos;
          cplx phase = 1;
          p[d] += u;
          p[e] -= v;
          if (p[d] == m.cells[d]) {
            p[d] = 0;
            phase *= m.wrap[d];
          }
          if (p[e] < 0) {
            p[e] += m.cells[e];
            phase *= std::conj(m.wrap[e]);
          }
          expected[count++] = {m.index(e, p), cross[d][e] * (u == v ? 1 : -1) * phase};
        }
    }
    std::sort(expected.begin(), expected.end(), [](const auto& x, const auto& y) { return x.first < y.first; });
    if (a.rowptr[row + 1] - a.rowptr[row] != count) {
      match = false;
      continue;
    }
    for (int j = 0; j < count; ++j) {
      const index_t q = a.rowptr[row] + j;
      match = match && a.colind[q] == expected[j].first && finite(a.values[q]) &&
              std::abs(a.values[q] - expected[j].second) <= threshold;
    }
  }
  why = match ? "periodic matrix stencil verified" : "full periodic stencil mismatch";
  return match;
}

struct Mode {
  std::array<index_t, 3> m{};
  double lambda = 0;
};
using Vector = std::array<cplx, 3>;
void normalize(Vector& v) {
  const double norm = std::hypot(std::abs(v[0]), std::abs(v[1]), std::abs(v[2]));
  for (auto& x : v) x /= norm;
}
}  // namespace

bool separable_curl_candidates(const CsrMatrix<cplx>& a, const CsrMatrix<cplx>* b, double sigma,
                               index_t k, double memory_bytes, DenseMatrix<cplx>& x,
                               std::vector<double>& lambda, std::vector<double>& hints,
                               std::string& why) {
  why = "invalid periodic candidate target";
  if (k < 1 || k > a.nrows || !std::isfinite(sigma)) return false;
  BlochModel model;
  if (!recognize(a, b, model, why)) return false;
  const double axes = static_cast<double>(model.cells[0]) + model.cells[1] + model.cells[2];
  const double need = static_cast<double>(model.volume) * (sizeof(Mode) + sizeof(double)) +
                      16.0 * a.nrows * static_cast<double>(k) + 16.0 * k * axes +
                      256.0 * k + 24.0 * axes + 4096.0;
  if (!(memory_bytes > 0) || !std::isfinite(memory_bytes) || !std::isfinite(need) || need > memory_bytes) {
    why = "periodic candidate workspace exceeds the available budget";
    return false;
  }
  const double pi = std::acos(-1.0);
  std::array<std::vector<cplx>, 3> symbol;
  for (int d = 0; d < 3; ++d) {
    symbol[d].resize(model.cells[d]);
    for (index_t j = 0; j < model.cells[d]; ++j) {
      const double theta = (model.phase[d] + 2 * pi * j) / model.cells[d];
      // exp(i theta)-1 without cancellation for a small phase.
      symbol[d][j] = 2 * std::sqrt(model.alpha[d]) * std::sin(0.5 * theta) *
                     cplx{-std::sin(0.5 * theta), std::cos(0.5 * theta)};
    }
  }
  std::vector<Mode> modes;
  modes.reserve(static_cast<std::size_t>(model.volume));
  for (index_t i = 0; i < model.cells[0]; ++i)
    for (index_t j = 0; j < model.cells[1]; ++j)
      for (index_t l = 0; l < model.cells[2]; ++l) {
        const double value = std::norm(symbol[0][i]) + std::norm(symbol[1][j]) + std::norm(symbol[2][l]);
        if (!std::isfinite(value)) {
          why = "nonfinite periodic modal value";
          return false;
        }
        if (value > 0) modes.push_back({{i, j, l}, value});
      }
  std::sort(modes.begin(), modes.end(), [&](const Mode& x, const Mode& y) {
    const double dx = std::abs(x.lambda - sigma), dy = std::abs(y.lambda - sigma);
    return dx != dy ? dx < dy : x.m < y.m;
  });
  why = "periodic target touches null space or incomplete multiplet";
  const std::size_t take = static_cast<std::size_t>(k / 2);
  if (k % 2 || take == 0 || take > modes.size()) return false;
  const double radius = std::abs(modes[take - 1].lambda - sigma);
  const double gap = 512 * std::numeric_limits<double>::epsilon() *
                     std::max(model.alpha[0] + model.alpha[1] + model.alpha[2], std::abs(sigma));
  if (std::abs(sigma) <= radius + gap ||
      (take < modes.size() && std::abs(modes[take].lambda - sigma) <= radius + gap))
    return false;
  struct Basis {
    std::array<std::vector<cplx>, 3> axes;
    std::array<Vector, 2> polarization;
  };
  std::vector<Basis> bases(take);
  for (std::size_t q = 0; q < take; ++q) {
    auto& basis = bases[q];
    Vector d;
    for (int axis = 0; axis < 3; ++axis) {
      const index_t mode = modes[q].m[axis], n = model.cells[axis];
      d[axis] = symbol[axis][mode];
      const double theta = (model.phase[axis] + 2 * pi * mode) / n;
      basis.axes[axis].resize(n);
      for (index_t j = 0; j < n; ++j)
        basis.axes[axis][j] = std::polar(1 / std::sqrt(static_cast<double>(n)), theta * j);
    }
    normalize(d);
    int axis = 0;
    for (int e = 1; e < 3; ++e)
      if (std::abs(d[e]) < std::abs(d[axis])) axis = e;
    auto& v = basis.polarization[0];
    for (int e = 0; e < 3; ++e) v[e] = (e == axis ? 1.0 : 0.0) - d[e] * std::conj(d[axis]);
    normalize(v);
    auto& w = basis.polarization[1];
    w = {std::conj(d[1] * v[2] - d[2] * v[1]), std::conj(d[2] * v[0] - d[0] * v[2]),
         std::conj(d[0] * v[1] - d[1] * v[0])};
    normalize(w);
  }
  x = DenseMatrix<cplx>(a.nrows, k);
  lambda.resize(k);
  bool all_finite = true;
#pragma omp parallel for reduction(&& : all_finite) schedule(static)
  for (index_t j = 0; j < k; ++j) {
    const auto& basis = bases[j / 2];
    lambda[j] = modes[j / 2].lambda;
    for (int orientation = 0; orientation < 3; ++orientation) {
      const cplx weight = basis.polarization[j % 2][orientation] / std::sqrt(model.mass[orientation]);
      index_t row = orientation * model.volume;
      for (cplx u : basis.axes[0])
        for (cplx v : basis.axes[1])
          for (cplx w : basis.axes[2]) {
            const cplx value = weight * u * v * w;
            all_finite = all_finite && finite(value);
            x(row++, j) = value;
          }
    }
  }
  if (!all_finite) {
    why = "nonfinite periodic candidate vector";
    return false;
  }
  hints.clear();
  hints.reserve(modes.size() + 1);
  hints.push_back(0);
  for (const auto& mode : modes) hints.push_back(mode.lambda);
  why = "verified Bloch matrix stencil " + std::to_string(model.cells[0]) + "x" +
        std::to_string(model.cells[1]) + "x" + std::to_string(model.cells[2]);
  return true;
}
}  // namespace hs::eigen_detail
