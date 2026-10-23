// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
// A matrix-verified separable Cartesian curl-curl candidate space (P25 measurements).
// D has +1 on its diagonal and -1 on its subdiagonal. Normalized node sine and cell cosine
// bases diagonalize D; each modal curl-curl block is ||s||^2 I - s s^T. The two transverse
// polarizations (one when a wave number vanishes) give candidates, never a completeness proof.
#include "eigen/separable_curl.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <string>
#include <utility>
#include <vector>

namespace hs::eigen_detail {
namespace {
struct Model {
  std::array<index_t, 3> cells{}, lengths{}, offsets{};
  std::array<double, 3> mass{}, alpha{};
  std::array<std::array<index_t, 3>, 3> shape{};
  index_t index(int d, const std::array<index_t, 3>& p) const {
    return offsets[d] + (p[0] * shape[d][1] + p[1]) * shape[d][2] + p[2];
  }
};

bool recognize(const CsrMatrix<double>& a, const CsrMatrix<double>* b, Model& m, std::string& why) {
  why = "first row";
  const index_t n = a.nrows;
  if (n < 36 || a.rowptr[1] != 7 || a.colind[0] != 0 || a.colind[1] != 1) return false;
  const index_t c = a.colind[2], lx = a.colind[3], ly = a.colind[5] - lx, lz = n - lx - ly;
  if (c < 2 || std::min({lx, ly, lz}) < 1 || (lx - ly) % c || lz % (c + 1)) return false;
  const index_t delta = (lx - ly) / c, prod = lz / (c + 1);
  const index_t disc = delta * delta + 4 * prod;
  const index_t q = static_cast<index_t>(std::sqrt(static_cast<long double>(disc)));
  const index_t nx = (q - delta) / 2 + 1, ny = nx + delta, nz = c + 1;
  why = "dimensions";
  if (q * q != disc || std::min({nx, ny, nz}) < 3) return false;
  auto product = [&](index_t x, index_t y, index_t z) {
    if (x > n / y || x * y > n / z) return index_t{0};
    return x * y * z;
  };
  if (product(nx, ny - 1, nz - 1) != lx || product(nx - 1, ny, nz - 1) != ly ||
      product(nx - 1, ny - 1, nz) != lz)
    return false;
  m.cells = {nx, ny, nz};
  m.lengths = {lx, ly, lz};
  m.offsets = {0, lx, lx + ly};
  for (int d = 0; d < 3; ++d)
    for (int j = 0; j < 3; ++j) m.shape[d][j] = m.cells[j] - (j == d ? 0 : 1);
  why = "diagonal block-constant mass";
  if (b && (b->nrows != n || b->nnz() != n)) return false;
  for (int d = 0; d < 3; ++d) {
    m.mass[d] = b ? b->values[m.offsets[d]] : 1.0;
    if (!std::isfinite(m.mass[d]) || m.mass[d] <= 0) return false;
    if (b) {
      for (index_t i = m.offsets[d]; i < m.offsets[d] + m.lengths[d]; ++i)
        if (b->rowptr[i] != i || b->rowptr[i + 1] != i + 1 || b->colind[i] != i ||
            b->values[i] != m.mass[d])
          return false;
    }
  }
  auto at = [&](index_t row, index_t col) {
    auto begin = a.colind.begin() + a.rowptr[row], end = a.colind.begin() + a.rowptr[row + 1];
    auto it = std::lower_bound(begin, end, col);
    return it == end || *it != col ? 0.0 : a.values[it - a.colind.begin()];
  };
  m.alpha = {-at(lx, lx + ny * c) / m.mass[1], -at(0, c) / m.mass[0], -at(0, 1) / m.mass[0]};
  why = "positive finite coefficients";
  for (double alpha : m.alpha)
    if (!std::isfinite(alpha) || alpha <= 0) return false;
  std::array<std::array<double, 3>, 3> cross{};
  std::array<double, 3> diagonal{};
  double largest = 0;
  for (int d = 0; d < 3; ++d) {
    for (int e = 0; e < 3; ++e) {
      if (e == d) continue;
      diagonal[d] += 2 * m.alpha[e] * m.mass[d];
      cross[d][e] = static_cast<double>(
          -std::sqrt(static_cast<long double>(m.alpha[d]) * m.alpha[e] * m.mass[d] * m.mass[e]));
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
    const int d = row < lx ? 0 : row < lx + ly ? 1 : 2;
    const index_t local = row - m.offsets[d];
    const std::array<index_t, 3> pos{local / (m.shape[d][1] * m.shape[d][2]),
                                     local / m.shape[d][2] % m.shape[d][1], local % m.shape[d][2]};
    std::array<std::pair<index_t, double>, 13> expected{};
    int count = 0;
    expected[count++] = {row, diagonal[d]};
    for (int e = 0; e < 3; ++e) {
      if (d == e) continue;
      for (int sign : {-1, 1}) {
        auto p = pos;
        p[e] += sign;
        if (p[e] >= 0 && p[e] < m.shape[d][e])
          expected[count++] = {m.index(d, p), -m.alpha[e] * m.mass[d]};
      }
      // D_d maps nodes -> cells: row i has +node_i and -node_(i-1).
      // D_e^T maps cells -> nodes: row j has +cell_j and -cell_(j+1).
      for (int u : {0, 1})
        for (int v : {0, 1}) {
          auto p = pos;
          p[d] -= u;
          p[e] += v;
          if (p[d] >= 0 && p[d] < m.shape[e][d])
            expected[count++] = {m.index(e, p), cross[d][e] * (u == v ? 1 : -1)};
        }
    }
    std::sort(expected.begin(), expected.begin() + count);
    if (a.rowptr[row + 1] - a.rowptr[row] != count) {
      match = false;
      continue;
    }
    for (int j = 0; j < count; ++j) {
      const index_t at = a.rowptr[row] + j;
      match = match && a.colind[at] == expected[j].first && std::isfinite(a.values[at]) &&
              std::abs(a.values[at] - expected[j].second) <= threshold;
    }
  }
  why = match ? "matrix stencil verified" : "full stencil mismatch";
  return match;
}

struct Mode {
  std::array<index_t, 3> m{};
  double lambda = 0;
  int multiplicity = 0;
};
std::array<double, 3> cross_product(const std::array<double, 3>& a,
                                    const std::array<double, 3>& b) {
  return {a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]};
}
void normalize(std::array<double, 3>& v) {
  const double norm = std::hypot(v[0], v[1], v[2]);
  for (auto& x : v) x /= norm;
}

}  // namespace

bool separable_curl_candidates(const CsrMatrix<double>& a, const CsrMatrix<double>* b, double sigma,
                               index_t k, double memory_bytes, DenseMatrix<double>& x,
                               std::vector<double>& lambda, std::vector<double>& hints,
                               std::string& why) {
  if (k < 1 || k > a.nrows || !std::isfinite(sigma)) {
    why = "invalid candidate target";
    return false;
  }
  Model model;
  if (!recognize(a, b, model, why)) return false;
  const index_t grid_size = model.cells[0] * model.cells[1] * model.cells[2];
  const index_t mode_count = grid_size - model.cells[0] - model.cells[1] - model.cells[2] + 2;
  const double axes = static_cast<double>(model.cells[0]) + model.cells[1] + model.cells[2];
  // Exact modal capacity, all chosen 1-D sine/cosine tables, output, hints and column metadata.
  // The caller has separately reserved its original-pencil verification buffers.
  const double need = static_cast<double>(mode_count) * (sizeof(Mode) + sizeof(double)) +
                      8.0 * a.nrows * static_cast<double>(k) + 16.0 * k * axes + 256.0 * k +
                      8.0 * axes + 4096.0;
  if (!(memory_bytes > 0) || !std::isfinite(memory_bytes) || !std::isfinite(need) ||
      need > memory_bytes) {
    why = "candidate workspace exceeds the available budget";
    return false;
  }
  const double pi = std::acos(-1.0);
  std::array<std::vector<double>, 3> s;
  for (int d = 0; d < 3; ++d) {
    s[d].resize(model.cells[d]);
    for (index_t j = 0; j < model.cells[d]; ++j)
      s[d][j] = 2 * std::sqrt(model.alpha[d]) * std::sin(j * pi / (2 * model.cells[d]));
  }
  std::vector<Mode> modes;
  modes.reserve(static_cast<std::size_t>(mode_count));
  for (index_t i = 0; i < model.cells[0]; ++i)
    for (index_t j = 0; j < model.cells[1]; ++j)
      for (index_t l = 0; l < model.cells[2]; ++l) {
        const int active = (i != 0) + (j != 0) + (l != 0);
        if (active < 2) continue;
        const double value = s[0][i] * s[0][i] + s[1][j] * s[1][j] + s[2][l] * s[2][l];
        if (!std::isfinite(value)) {
          why = "nonfinite modal value";
          return false;
        }
        modes.push_back({{i, j, l}, value, active == 3 ? 2 : 1});
      }
  std::sort(modes.begin(), modes.end(), [&](const Mode& a, const Mode& b) {
    const double da = std::abs(a.lambda - sigma), db = std::abs(b.lambda - sigma);
    return da != db ? da < db : a.m < b.m;
  });
  index_t count = 0;
  std::size_t take = 0;
  while (take < modes.size() && count < k) count += modes[take++].multiplicity;
  why = "target touches null space or incomplete multiplet";
  if (count != k || take == 0) return false;
  const double radius = std::abs(modes[take - 1].lambda - sigma);
  const double gap = 512 * std::numeric_limits<double>::epsilon() *
                     std::max(model.alpha[0] + model.alpha[1] + model.alpha[2], std::abs(sigma));
  if (std::abs(sigma) <= radius + gap ||
      (take < modes.size() && std::abs(modes[take].lambda - sigma) <= radius + gap))
    return false;
  struct Column {
    Mode mode;
    std::array<double, 3> polarization;
  };
  std::vector<Column> columns;
  columns.reserve(static_cast<std::size_t>(k));
  for (std::size_t j = 0; j < take; ++j) {
    const Mode& mode = modes[j];
    std::array<double, 3> v{}, w{s[0][mode.m[0]], s[1][mode.m[1]], s[2][mode.m[2]]};
    if (mode.multiplicity == 1) {
      for (int d = 0; d < 3; ++d)
        if (mode.m[d] == 0) v[d] = 1;
      columns.push_back({mode, v});
    } else {
      int axis = 0;
      for (int d = 1; d < 3; ++d)
        if (std::abs(w[d]) < std::abs(w[axis])) axis = d;
      v[axis] = 1;
      v = cross_product(w, v);
      normalize(v);
      columns.push_back({mode, v});
      v = cross_product(w, v);
      normalize(v);
      columns.push_back({mode, v});
    }
  }
  // Allocate the tables outside the OpenMP region: bad_alloc must reach the driver's
  // fallback rather than terminate a worker. Columns of one mode share the same tables.
  struct Basis {
    std::array<std::vector<double>, 3> sine, cosine;
  };
  std::vector<Basis> bases(take);
  std::vector<std::size_t> column_mode;
  column_mode.reserve(static_cast<std::size_t>(k));
  for (std::size_t q = 0; q < take; ++q) {
    for (int d = 0; d < 3; ++d) {
      const index_t n = model.cells[d], mode = modes[q].m[d];
      auto& sine = bases[q].sine[d];
      auto& cosine = bases[q].cosine[d];
      sine.resize(static_cast<std::size_t>(n - 1));
      cosine.resize(static_cast<std::size_t>(n));
      for (index_t i = 0; i < n - 1; ++i)
        sine[i] = std::sqrt(2.0 / n) * std::sin(mode * pi * (i + 1) / n);
      for (index_t i = 0; i < n; ++i)
        cosine[i] = mode == 0 ? 1 / std::sqrt(static_cast<double>(n))
                              : std::sqrt(2.0 / n) * std::cos(mode * pi * (i + .5) / n);
    }
    for (int p = 0; p < modes[q].multiplicity; ++p) column_mode.push_back(q);
  }
  x = DenseMatrix<double>(a.nrows, k);
  lambda.resize(k);
  bool finite = true;
#pragma omp parallel for reduction(&& : finite) schedule(static)
  for (index_t j = 0; j < k; ++j) {
    const auto& col = columns[j];
    const auto& basis = bases[column_mode[j]];
    lambda[j] = col.mode.lambda;
    for (int orientation = 0; orientation < 3; ++orientation) {
      const auto& xbasis = orientation == 0 ? basis.cosine[0] : basis.sine[0];
      const auto& ybasis = orientation == 1 ? basis.cosine[1] : basis.sine[1];
      const auto& zbasis = orientation == 2 ? basis.cosine[2] : basis.sine[2];
      const double weight = col.polarization[orientation] / std::sqrt(model.mass[orientation]);
      index_t row = model.offsets[orientation];
      for (double u : xbasis)
        for (double v : ybasis)
          for (double w : zbasis) {
            const double value = weight * u * v * w;
            finite = finite && std::isfinite(value);
            x(row++, j) = value;
          }
    }
  }
  if (!finite) {
    why = "nonfinite candidate vector";
    return false;
  }
  hints.clear();
  hints.reserve(modes.size() + 1);
  hints.push_back(0);
  for (const auto& mode : modes) hints.push_back(mode.lambda);
  why = "verified matrix stencil " + std::to_string(model.cells[0]) + "x" +
        std::to_string(model.cells[1]) + "x" + std::to_string(model.cells[2]);
  return true;
}

}  // namespace hs::eigen_detail
