// Eigenvector subspace-angle bounds (src/driver/subspace.hpp; docs/DESIGN.md §3.6-8c).
#include "driver/subspace.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <new>
#include <numeric>
#include <string>
#include <vector>

#include "driver/internal.hpp"
#include "driver/norms.hpp"
#include "hsolve/error.hpp"
#include "hsolve/factor.hpp"
#include "hsolve/sparse.hpp"
#include "hsolve/util.hpp"
#include "linalg/blas_lapack.hpp"
#include "linalg/dense_ops.hpp"

namespace hs::driver {

namespace {

constexpr double kInfinity = std::numeric_limits<double>::infinity();
constexpr double kNaN = std::numeric_limits<double>::quiet_NaN();
constexpr double kRoundoff = 0x1p-53;
/// Columns per chunk of the residual and CG blocks (at most).
constexpr index_t kChunkColumns = 16;
/// A group whose Gram defect reaches this is not numerically independent: no bound.
constexpr double kMaxOrthogonalityDefect = 0.5;
/// CG for r^H B^{-1} r stops once its remainder estimate (s^H B^{-1} s, bounded through
/// lambda_min(B) and lambda_min(S)) is at most this share of the quadratic form: the residual norm
/// is then inflated by at most half of it (0.5%), far below the bound's own slack.
constexpr double kRemainderShare = 1e-2;

/// gamma_k = k u / (1 - k u) of Higham (Accuracy and Stability, §3.1), with a factor 2 of slack
/// that also covers complex arithmetic.
double gamma_of(double k) {
  const double t = 2.0 * k * kRoundoff;
  return t < 0.5 ? t / (1.0 - t) : kInfinity;
}

/// max_i sum_j |m_ij| (an upper bound of || |M| ||_2 for Hermitian M, rounding of the sums
/// included) and the longest row.
struct RowStats {
  double abs_sum = 1.0;
  index_t max_nnz = 1;
};

template <class T>
RowStats row_stats(const CsrMatrix<T>& m) {
  double sum_max = 0.0;
  index_t len_max = 0;
#pragma omp parallel for reduction(max : sum_max, len_max) schedule(static)
  for (index_t i = 0; i < m.nrows; ++i) {
    double s = 0.0;
    for (index_t p = m.rowptr[i]; p < m.rowptr[i + 1]; ++p) s += std::abs(m.values[p]);
    sum_max = std::max(sum_max, s);
    len_max = std::max(len_max, m.rowptr[i + 1] - m.rowptr[i]);
  }
  return {sum_max * (1.0 + gamma_of(static_cast<double>(len_max) + 1.0)), std::max<index_t>(len_max, 1)};
}

double real_part(double v) { return v; }
double real_part(const cplx& v) { return v.real(); }

/// inv_diag[i] = 1 / b_ii (b_ii real and positive for an HPD B; +inf otherwise, which makes the
/// caller's bound infinite).
template <class T>
std::vector<double> inverse_diagonal(const CsrMatrix<T>& b) {
  std::vector<double> inv(static_cast<std::size_t>(b.nrows), kInfinity);
#pragma omp parallel for schedule(static)
  for (index_t i = 0; i < b.nrows; ++i)
    for (index_t p = b.rowptr[i]; p < b.rowptr[i + 1]; ++p)
      if (b.colind[p] == i) {
        const double d = real_part(b.values[p]);
        if (d > 0.0) inv[static_cast<std::size_t>(i)] = 1.0 / d;
      }
  return inv;
}

/// |v| to within 2u: sqrt(re^2 + im^2) without the scaling of std::abs (hypot), which costs an
/// order of magnitude more; the envelopes below carry slack for this rounding.
inline double magnitude(double v) { return std::fabs(v); }
inline double magnitude(const cplx& v) { return std::sqrt(v.real() * v.real() + v.imag() * v.imag()); }

/// out(:, j) = |v(:, j)| for the p columns of v (n x p, ld n; out ld n).
template <class T>
void magnitudes(const T* v, index_t n, index_t p, double* out) {
#pragma omp parallel for schedule(static)
  for (index_t i = 0; i < n; ++i)
    for (index_t j = 0; j < p; ++j) out[i + j * n] = magnitude(v[i + j * n]);
}

/// out(i, j) = sum_k |m_ik| absv(k, j) for the p columns of absv (n x p, ld n; out ld n): the
/// componentwise envelope |M| |V| (the rounding error of a computed M v is at most gamma_{len+1}
/// times it in row i). One pass over M for all columns.
template <class T>
void abs_spmm(const CsrMatrix<T>& m, const double* absv, index_t p, double* out) {
  const index_t n = m.nrows;
#pragma omp parallel
  {
    std::vector<double> acc(static_cast<std::size_t>(p));
#pragma omp for schedule(static)
    for (index_t i = 0; i < n; ++i) {
      std::fill(acc.begin(), acc.end(), 0.0);
      for (index_t q = m.rowptr[i]; q < m.rowptr[i + 1]; ++q) {
        const double mv = magnitude(m.values[q]);
        const double* vk = absv + m.colind[q];
        for (index_t j = 0; j < p; ++j) acc[static_cast<std::size_t>(j)] += mv * vk[j * n];
      }
      for (index_t j = 0; j < p; ++j) out[i + j * n] = acc[static_cast<std::size_t>(j)];
    }
  }
}

/// How B^{-1}-norms are bounded: B = I (identity), a diagonal B (exact weights 1 / b_ii), or a
/// general HPD B through lower bounds of lambda_min(B) (b_min) and of lambda_min(S),
/// S = D^{-1/2} B D^{-1/2} (scaled; 0 = none).
struct BInverseWeights {
  bool identity = true;
  bool diagonal = false;
  const std::vector<double>* inv_diag = nullptr;
  double b_min = 1.0;
  double scaled = 0.0;
};

/// An upper bound of sqrt(v^H B^{-1} v) for every v with |v_i| <= c_i (c >= 0): ||c||_2 (B = I),
/// sqrt(sum c_i^2 / b_ii) (diagonal B), else the smaller of ||c||_2 / sqrt(lambda_min(B)) and
/// ||D^{-1/2} c||_2 / sqrt(lambda_min(S)), since v^H B^{-1} v = (D^{-1/2} v)^H S^{-1} (D^{-1/2} v).
/// The rounding of the sums is included.
double envelope_b_inverse_norm(const double* c, index_t n, const BInverseWeights& w) {
  double plain = 0.0, weighted = 0.0;
  const double* inv = !w.identity && (w.diagonal || w.scaled > 0.0) ? w.inv_diag->data() : nullptr;
#pragma omp parallel for reduction(+ : plain, weighted) schedule(static)
  for (index_t i = 0; i < n; ++i) {
    const double c2 = c[i] * c[i];
    plain += c2;
    if (inv) weighted += c2 * inv[i];
  }
  const double slack = 1.0 + gamma_of(static_cast<double>(n) + 4.0);
  if (w.identity) return std::sqrt(plain) * slack;
  if (w.diagonal) return std::sqrt(weighted) * slack;
  double bound = std::sqrt(plain / w.b_min);
  if (w.scaled > 0.0) bound = std::min(bound, std::sqrt(weighted / w.scaled));
  return bound * slack;
}

/// Rows per block of the fused CG passes: the per-column partial sums are formed on these fixed
/// blocks and added in block order, so the sums do not depend on the number of threads.
constexpr index_t kCgBlockRows = 2048;

/// Re conj(a) b.
inline double re_dot(double a, double b) { return a * b; }
inline double re_dot(const cplx& a, const cplx& b) { return a.real() * b.real() + a.imag() * b.imag(); }

/// One fused pass of the block CG: f(j, i0, i1, acc) for every column j with active[j], on the
/// fixed row blocks [i0, i1) in parallel; acc points to the column's `width` partial sums of the
/// block, which come back added in block order (sums[j * width + k]).
template <class F>
void fused_pass(index_t n, index_t p, const std::vector<char>& active, int width, std::vector<double>& part,
                std::vector<double>& sums, const F& f) {
  const index_t blocks = (n + kCgBlockRows - 1) / kCgBlockRows;
  const auto stride = static_cast<std::size_t>(p) * static_cast<std::size_t>(width);
  part.assign(static_cast<std::size_t>(blocks) * stride, 0.0);
#pragma omp parallel for schedule(static)
  for (index_t blk = 0; blk < blocks; ++blk) {
    const index_t i0 = blk * kCgBlockRows, i1 = std::min(n, i0 + kCgBlockRows);
    double* acc = part.data() + static_cast<std::size_t>(blk) * stride;
    for (index_t j = 0; j < p; ++j)
      if (active[static_cast<std::size_t>(j)]) f(j, i0, i1, acc + static_cast<std::size_t>(j) * width);
  }
  sums.assign(stride, 0.0);
  for (index_t blk = 0; blk < blocks; ++blk)
    for (std::size_t k = 0; k < stride; ++k) sums[k] += part[static_cast<std::size_t>(blk) * stride + k];
}

/// Upper bounds q_j >= r_j^H B^{-1} r_j for the p columns of r (n x p, ld n), B HPD. For any z,
/// with s = r - B z:  r^H B^{-1} r = Re z^H (2 r - B z) + s^H B^{-1} s, where s^H B^{-1} s is bounded
/// by envelope_b_inverse_norm (lower bounds, or estimates, of lambda_min(B) and lambda_min(S)).
/// z comes from Jacobi-preconditioned CG (it only makes s small; the identity holds for any z),
/// run on all columns at once with their own step sizes: one product with B and three fused passes
/// over the columns per iteration. The evaluation's rounding is bounded a priori, componentwise for
/// the products with B.
template <class T>
void cg_b_inverse_quadratic(const CsrMatrix<T>& b, const BInverseWeights& wts, const RowStats& sb, const T* r,
                            index_t n, index_t p, const SubspaceOptions& opt, double* q) {
  const double* inv_diag = wts.inv_diag->data();
  DenseMatrix<T> z(n, p), s(n, p), h(n, p), dir(n, p), bd(n, p);
  const auto np = static_cast<std::size_t>(p);
  std::vector<double> rnorm(np), rho(np), alpha(np), beta(np);
  std::vector<double> quad(np, 0.0);  // r^H z_k = sum_i alpha_i rho_i
  std::vector<char> active(np, 1);
  std::vector<double> part, sums;
  // s = r, h = D^{-1} s, dir = h; ||r||^2 and rho = s^H h.
  fused_pass(n, p, active, 2, part, sums, [&](index_t j, index_t i0, index_t i1, double* acc) {
    const T* rj = r + j * n;
    T* sj = s.col(j);
    T* hj = h.col(j);
    T* dj = dir.col(j);
    for (index_t i = i0; i < i1; ++i) {
      sj[i] = rj[i];
      hj[i] = rj[i] * inv_diag[i];
      dj[i] = hj[i];
      acc[0] += std::norm(rj[i]);
      acc[1] += re_dot(rj[i], hj[i]);
    }
  });
  for (std::size_t j = 0; j < np; ++j) {
    rnorm[j] = std::sqrt(sums[2 * j]);
    rho[j] = sums[2 * j + 1];
    active[j] = rnorm[j] > 0.0 && rho[j] > 0.0;
  }
  const Timer cg_timer;
  int it = 0;
  for (; it < opt.cg_max_iterations; ++it) {
    if (std::none_of(active.begin(), active.end(), [](char a) { return a != 0; })) break;
    spmm(b, dir.data(), n, bd.data(), n, p);
    // Curvatures dir^H B dir.
    fused_pass(n, p, active, 1, part, sums, [&](index_t j, index_t i0, index_t i1, double* acc) {
      const T* dj = dir.col(j);
      const T* bj = bd.col(j);
      for (index_t i = i0; i < i1; ++i) acc[0] += re_dot(dj[i], bj[i]);
    });
    for (std::size_t j = 0; j < np; ++j) {
      if (!active[j]) continue;
      if (!(sums[j] > 0.0)) {  // breakdown: the bound below holds for the current z
        active[j] = 0;
        continue;
      }
      alpha[j] = rho[j] / sums[j];
      quad[j] += alpha[j] * rho[j];
    }
    // z += alpha dir, s -= alpha B dir, h = D^{-1} s; ||s||^2 and ||D^{-1/2} s||^2 = s^H h.
    fused_pass(n, p, active, 2, part, sums, [&](index_t j, index_t i0, index_t i1, double* acc) {
      const double a = alpha[static_cast<std::size_t>(j)];
      const T* dj = dir.col(j);
      const T* bj = bd.col(j);
      T* zj = z.col(j);
      T* sj = s.col(j);
      T* hj = h.col(j);
      for (index_t i = i0; i < i1; ++i) {
        zj[i] += a * dj[i];
        sj[i] -= a * bj[i];
        hj[i] = sj[i] * inv_diag[i];
        acc[0] += std::norm(sj[i]);
        acc[1] += re_dot(sj[i], hj[i]);
      }
    });
    for (std::size_t j = 0; j < np; ++j) {
      if (!active[j]) continue;
      const double snorm2 = sums[2 * j], rho_next = sums[2 * j + 1];
      // Enough once the remainder's estimate, s^H B^{-1} s <= min(||s||^2 / lambda_min(B),
      // ||D^{-1/2} s||^2 / lambda_min(S)), is a negligible share of r^H B^{-1} r (approached from
      // below by CG's r^H z_k), or s is at rounding level.
      double remainder = snorm2 / wts.b_min;
      if (wts.scaled > 0.0) remainder = std::min(remainder, rho_next / wts.scaled);
      if (remainder <= kRemainderShare * quad[j] || std::sqrt(snorm2) <= opt.cg_tol * rnorm[j] || !(rho_next > 0.0)) {
        active[j] = 0;
        continue;
      }
      beta[j] = rho_next / rho[j];
      rho[j] = rho_next;
    }
    // dir = h + beta dir.
    fused_pass(n, p, active, 0, part, sums, [&](index_t j, index_t i0, index_t i1, double*) {
      const double bt = beta[static_cast<std::size_t>(j)];
      const T* hj = h.col(j);
      T* dj = dir.col(j);
      for (index_t i = i0; i < i1; ++i) dj[i] = hj[i] + bt * dj[i];
    });
  }
  if (opt.diagnostics) {
    opt.diagnostics->cg_s += cg_timer.seconds();
    opt.diagnostics->cg_iterations = std::max(opt.diagnostics->cg_iterations, it);
  }
  // The identity with the explicit s = r - B z (not CG's recurrence).
  spmm(b, z.data(), n, bd.data(), n, p);
  const double g_n = gamma_of(static_cast<double>(n) + 2.0);
  const double g_b = gamma_of(static_cast<double>(sb.max_nnz) + 1.0);
  std::vector<double> abs_z(np * static_cast<std::size_t>(n)), abs_bz_all(np * static_cast<std::size_t>(n));
  magnitudes(z.data(), n, p, abs_z.data());
  abs_spmm(b, abs_z.data(), p, abs_bz_all.data());
  for (index_t j = 0; j < p; ++j) {
    const T* rj = r + j * n;
    const T* zj = z.col(j);
    const T* wj = bd.col(j);
    T* sj = s.col(j);
#pragma omp parallel for schedule(static)
    for (index_t i = 0; i < n; ++i) sj[i] = rj[i] - wj[i];
    const double zn = linalg::norm2(n, zj), wn = linalg::norm2(n, wj);
    const double rn = rnorm[static_cast<std::size_t>(j)];
    const double main = 2.0 * real_part(linalg::dot(n, zj, rj)) - real_part(linalg::dot(n, zj, wj));
    // w = fl(B z) is within g_b |B| |z| of B z componentwise, so
    // |fl(main) - z^H (2 r - B z)| <= gamma_n ||z|| (2 ||r|| + ||w||) + g_b ||z|| || |B| |z| ||, and
    // the exact r - B z is at most |s_i| (1 + 2u) + g_b (|B| |z|)_i in modulus.
    double* env = abs_bz_all.data() + static_cast<std::size_t>(j) * static_cast<std::size_t>(n);
    const double abs_bz = linalg::norm2(n, env) * (1.0 + g_n);
    const double main_err = g_n * zn * (2.0 * rn + wn) + g_b * zn * abs_bz;
#pragma omp parallel for schedule(static)
    for (index_t i = 0; i < n; ++i) env[i] = magnitude(sj[i]) * (1.0 + 4.0 * kRoundoff) + g_b * env[i];
    const double remainder = envelope_b_inverse_norm(env, n, wts);
    q[j] = std::max(0.0, main + main_err) + remainder * remainder;
  }
}

/// eps >= ||X_c^H B X_c - I||_2 for the columns `cols` (column(j): the j-th vector, n entries): the
/// Frobenius norm of the computed defect plus the a-priori bound of the Gram entries' rounding,
/// |g_ij - fl(g_ij)| <= gamma_{n+m} ||x_i|| || |B| |x_j| || (abs_b[j] >= || |B| |x_j| ||, the
/// vector's norm for B = I). Blocks of at most `width` columns.
template <class T, class Column>
double gram_defect(const CsrMatrix<T>* b, const RowStats& sb, index_t n, const Column& column,
                   const std::vector<index_t>& cols, const std::vector<double>& abs_b, index_t width) {
  const auto m = static_cast<index_t>(cols.size());
  const index_t w = std::max<index_t>(1, std::min(width, m));
  DenseMatrix<T> xi(n, w), xj(n, w), bxj(n, w), g(w, w);
  const auto gather = [&](DenseMatrix<T>& dst, index_t first, index_t count) {
#pragma omp parallel for schedule(static)
    for (index_t c = 0; c < count; ++c) {
      const T* src = column(cols[static_cast<std::size_t>(first + c)]);
      std::copy(src, src + n, dst.col(c));
    }
  };
  double defect2 = 0.0, norms2 = 0.0, abs2 = 0.0;
  for (index_t c : cols) {
    const double v = linalg::norm2(n, column(c));
    const double a = abs_b[static_cast<std::size_t>(c)];
    norms2 += v * v;
    abs2 += a * a;
  }
  for (index_t j0 = 0; j0 < m; j0 += w) {
    const index_t pj = std::min(w, m - j0);
    gather(xj, j0, pj);
    if (b)
      spmm(*b, xj.data(), n, bxj.data(), n, pj);
    else
      std::copy(xj.data(), xj.data() + n * pj, bxj.data());
    for (index_t i0 = 0; i0 < m; i0 += w) {
      const index_t pi = std::min(w, m - i0);
      const T* left = xj.data();
      if (i0 != j0) {
        gather(xi, i0, pi);
        left = xi.data();
      }
      lapack::gemm('C', 'N', static_cast<lapack::fint>(pi), static_cast<lapack::fint>(pj),
                   static_cast<lapack::fint>(n), T(1), left, static_cast<lapack::fint>(n), bxj.data(),
                   static_cast<lapack::fint>(n), T(0), g.data(), static_cast<lapack::fint>(w));
      for (index_t jj = 0; jj < pj; ++jj)
        for (index_t ii = 0; ii < pi; ++ii) {
          const T e = g(ii, jj) - (i0 + ii == j0 + jj ? T(1) : T(0));
          defect2 += std::norm(e);
        }
    }
  }
  const double slack = 1.0 + gamma_of(static_cast<double>(m * m + n) + 2.0);
  const double rounding = gamma_of(static_cast<double>(n + sb.max_nnz) + 2.0) * std::sqrt(norms2 * abs2);
  return (std::sqrt(defect2) + rounding) * slack;
}

/// One group of pairs (indices into the returned pairs, then the unreturned ones) with its Kahan
/// quantities.
struct Group {
  std::vector<index_t> pairs;  // ascending lambda
  double lo = 0.0, hi = 0.0;   // min / max lambda
  double residual = 0.0;       // sqrt(sum rho^2)
  double eps = 0.0;            // Gram defect
  double eta = 0.0;            // Kahan radius
};

}  // namespace

template <class T>
GershgorinBounds gershgorin_bounds(const CsrMatrix<T>& b) {
  const index_t n = b.nrows;
  GershgorinBounds out;
  if (n == 0) return out;
  std::vector<double> diag(static_cast<std::size_t>(n), 0.0);
#pragma omp parallel for schedule(static)
  for (index_t i = 0; i < n; ++i)
    for (index_t p = b.rowptr[i]; p < b.rowptr[i + 1]; ++p)
      if (b.colind[p] == i) diag[static_cast<std::size_t>(i)] = real_part(b.values[p]);
  double plain = kInfinity, scaled = kInfinity, dmin = kInfinity;
#pragma omp parallel for reduction(min : plain, scaled, dmin) schedule(static)
  for (index_t i = 0; i < n; ++i) {
    const double d = diag[static_cast<std::size_t>(i)];
    double off = 0.0, off_scaled = 0.0;
    for (index_t p = b.rowptr[i]; p < b.rowptr[i + 1]; ++p) {
      const index_t j = b.colind[p];
      if (j == i) continue;
      const double dj = diag[static_cast<std::size_t>(j)];
      off += std::abs(b.values[p]);
      off_scaled += d > 0.0 && dj > 0.0 ? std::abs(b.values[p]) / std::sqrt(d * dj) : kInfinity;
    }
    // Each term carries a few roundings, the sum one per term: gamma_{len + 4} covers both.
    const double g = gamma_of(static_cast<double>(b.rowptr[i + 1] - b.rowptr[i]) + 4.0);
    plain = std::min(plain, d - off * (1.0 + g));
    scaled = std::min(scaled, 1.0 - off_scaled * (1.0 + g));
    dmin = std::min(dmin, d);
  }
  out.min_diagonal = dmin;
  if (!(dmin > 0.0)) return out;
  out.plain = plain * (1.0 - 4.0 * kRoundoff);
  out.scaled = scaled * (1.0 - 4.0 * kRoundoff);
  return out;
}

template <class T>
double gershgorin_lambda_min(const CsrMatrix<T>& b) {
  const GershgorinBounds g = gershgorin_bounds(b);
  // Jacobi scaling D^{-1/2}: x^H B x = y^H S y with y = D^{1/2} x and ||y||^2 >= min_i b_ii ||x||^2,
  // so lambda_min(B) >= lambda_min(S) min_i b_ii.
  const double from_scaled = g.scaled > 0.0 ? g.scaled * g.min_diagonal * (1.0 - 4.0 * kRoundoff) : 0.0;
  return std::max(std::max(g.plain, from_scaled), 0.0);
}

template <class T>
std::vector<double> residual_b_inverse_norms(const CsrMatrix<T>& a, const CsrMatrix<T>* b,
                                             const std::vector<double>& lambda, const DenseMatrix<T>& x,
                                             const SubspaceOptions& opt, std::vector<double>* abs_b_norms) {
  const index_t n = x.rows(), m = x.cols();
  std::vector<double> rho(static_cast<std::size_t>(m), 0.0);
  if (abs_b_norms) abs_b_norms->assign(static_cast<std::size_t>(m), 0.0);
  if (m == 0) return rho;
  const RowStats sa = row_stats(a);
  const RowStats sb = b ? row_stats(*b) : RowStats{};
  const bool cg = b != nullptr && !opt.b_diagonal;
  // Per column: A x, the residual (CG: five more blocks), and the envelopes |x|, |A| |x|, |B| |x|
  // (CG: |z|, |B| |z|). Half the memory left for the column chunks: the rest stays free for the
  // allocator's and the libraries' own use.
  const double per_column = static_cast<double>(n) * ((cg ? 7.0 : 2.0) * sizeof(T) + (cg ? 5.0 : 3.0) * sizeof(double));
  const double fit = std::floor(0.5 * opt.memory_bytes / per_column);
  if (!(fit >= 1.0))
    HS_THROW(OutOfMemoryBudget, "subspace bound: one column's workspace (" << per_column / 1e6 << " MB) exceeds the "
                                                                          << opt.memory_bytes / 1e6 << " MB left");
  const index_t w = std::min<index_t>({m, kChunkColumns, static_cast<index_t>(std::min(fit, 1e9))});
  const std::vector<double> inv_diag = b ? inverse_diagonal(*b) : std::vector<double>{};
  BInverseWeights wts;
  if (b) {
    wts.identity = false;
    wts.diagonal = opt.b_diagonal;
    wts.inv_diag = &inv_diag;
    wts.b_min = opt.b_min.value;
    wts.scaled = opt.b_min.scaled;
  }
  const double g_res = gamma_of(static_cast<double>(std::max(sa.max_nnz, sb.max_nnz)) + 4.0);
  const double g_n = gamma_of(static_cast<double>(n) + 4.0);
  DenseMatrix<T> ax(n, w), res(n, w);
  const auto block = static_cast<std::size_t>(n) * static_cast<std::size_t>(w);
  std::vector<double> q(static_cast<std::size_t>(w)), abs_x(block), env_a(block), env_b(b ? block : 0);
  for (index_t j0 = 0; j0 < m; j0 += w) {
    const index_t p = std::min(w, m - j0);
    spmm(a, x.col(j0), n, ax.data(), n, p);
    if (b)
      spmm(*b, x.col(j0), n, res.data(), n, p);
    else
      std::copy(x.col(j0), x.col(j0) + n * p, res.data());
    for (index_t j = 0; j < p; ++j) {
      const double l = lambda[static_cast<std::size_t>(j0 + j)];
      const T* axj = ax.col(j);
      T* rj = res.col(j);
#pragma omp parallel for schedule(static)
      for (index_t i = 0; i < n; ++i) rj[i] = axj[i] - l * rj[i];
    }
    if (cg) cg_b_inverse_quadratic(*b, wts, sb, res.data(), n, p, opt, q.data());
    // The residual's own rounding, componentwise: |r - fl(r)| <= gamma_{m+4} (|A| |x| + |lambda| |B| |x|)
    // (the envelopes' evaluation adds at most gamma_{m+3} relative, covered by the factor 1 + g_res).
    magnitudes(x.col(j0), n, p, abs_x.data());
    abs_spmm(a, abs_x.data(), p, env_a.data());
    if (b) abs_spmm(*b, abs_x.data(), p, env_b.data());
    const std::vector<double>& abs_bx = b ? env_b : abs_x;
    for (index_t j = 0; j < p; ++j) {
      const auto jj = static_cast<std::size_t>(j0 + j);
      const T* rj = res.col(j);
      double* ea = env_a.data() + static_cast<std::size_t>(j) * static_cast<std::size_t>(n);
      const double* eb = abs_bx.data() + static_cast<std::size_t>(j) * static_cast<std::size_t>(n);
      if (abs_b_norms) (*abs_b_norms)[jj] = linalg::norm2(n, eb) * (1.0 + g_res) * (1.0 + g_n);
      const double scale = g_res * (1.0 + g_res), al = std::abs(lambda[jj]);
#pragma omp parallel for schedule(static)
      for (index_t i = 0; i < n; ++i) ea[i] = scale * (ea[i] + al * eb[i]);
      const double rounding = envelope_b_inverse_norm(ea, n, wts);
      double norm = 0.0;
      if (!b) {
        norm = linalg::norm2(n, rj) * (1.0 + g_n);
      } else if (!cg) {
        double sum = 0.0;
#pragma omp parallel for reduction(+ : sum) schedule(static)
        for (index_t i = 0; i < n; ++i) sum += std::norm(rj[i]) * inv_diag[static_cast<std::size_t>(i)];
        norm = std::sqrt(sum) * (1.0 + g_n);
      } else {
        norm = std::sqrt(q[static_cast<std::size_t>(j)]) * (1.0 + g_n);
      }
      rho[jj] = norm + rounding;
      if (!std::isfinite(rho[jj])) rho[jj] = kInfinity;
    }
  }
  return rho;
}

template <class T>
SubspaceReport subspace_bounds(const CsrMatrix<T>& a, const CsrMatrix<T>* b, const std::vector<double>& returned,
                               const DenseMatrix<T>& x, const std::vector<double>& unreturned,
                               const DenseMatrix<T>& extra, const std::vector<CertifiedWindow>& windows,
                               const SubspaceOptions& opt, std::vector<double>& per_pair) {
  const index_t n = a.nrows, m = static_cast<index_t>(returned.size());
  const auto e = static_cast<index_t>(unreturned.size());
  if (x.cols() != m || (m > 0 && x.rows() != n) || extra.cols() != e || (e > 0 && extra.rows() != n))
    HS_THROW(Internal, "subspace bound: " << x.cols() << " + " << extra.cols() << " vectors for " << m << " + " << e
                                          << " eigenvalues");
  SubspaceReport rep;
  rep.performed = true;
  rep.residual_norm = !b ? "2" : opt.b_diagonal ? "b_inverse_diagonal" : "b_inverse_cg";
  rep.b_min = b ? opt.b_min.value : 1.0;
  rep.b_min_source = b ? opt.b_min.source : "identity";
  rep.rigorous = !b || opt.b_min.proven;
  per_pair.assign(static_cast<std::size_t>(m), kNaN);
  if (m == 0) {
    rep.note = "no pairs returned";
    return rep;
  }
  // Pair j < m is returned pair j, pair m + i the unreturned pair i.
  std::vector<double> lambda = returned;
  lambda.insert(lambda.end(), unreturned.begin(), unreturned.end());
  const Timer residual_timer;
  std::vector<double> abs_b;  // || |B| |x_j| || per pair (the Gram rounding)
  std::vector<double> rho = residual_b_inverse_norms(a, b, returned, x, opt, &abs_b);
  if (e > 0) {
    std::vector<double> abs_b_extra;
    const std::vector<double> rho_extra = residual_b_inverse_norms(a, b, unreturned, extra, opt, &abs_b_extra);
    rho.insert(rho.end(), rho_extra.begin(), rho_extra.end());
    abs_b.insert(abs_b.end(), abs_b_extra.begin(), abs_b_extra.end());
  }
  if (opt.diagnostics) opt.diagnostics->residual_s += residual_timer.seconds();
  const auto column = [&](index_t j) { return j < m ? x.col(j) : extra.col(j - m); };
  const RowStats sb = b ? row_stats(*b) : RowStats{};
  const double per_column = 3.0 * static_cast<double>(n) * sizeof(T);
  const auto gram_width = static_cast<index_t>(
      std::clamp(std::floor(0.5 * opt.memory_bytes / per_column), 1.0, static_cast<double>(kChunkColumns) * 4.0));

  std::vector<std::string> issues;
  const auto describe = [&](const Group& g, double gap, const std::string& kind, double lower, double upper,
                            index_t dimension) {
    SubspaceGroup out;
    out.kind = kind;
    for (index_t j : g.pairs) {
      if (j < m)
        out.pairs.push_back(j);
      else
        ++out.unreturned;
    }
    if (out.pairs.empty()) return;  // only pairs the target does not return
    out.lower = lower;
    out.upper = upper;
    out.dimension = dimension;
    out.gap = gap;
    out.residual = g.residual;
    out.orthogonality = g.eps;
    const double bound = g.residual / (gap * std::sqrt(1.0 - g.eps));
    out.sin_bound = gap > 0.0 && g.eps < kMaxOrthogonalityDefect && std::isfinite(bound) ? std::min(bound, 1.0) : kNaN;
    for (index_t j : out.pairs) per_pair[static_cast<std::size_t>(j)] = out.sin_bound;
    rep.groups.push_back(std::move(out));
  };
  const auto measure = [&](Group& g) {
    double r2 = 0.0;
    g.lo = kInfinity;
    g.hi = -kInfinity;
    for (index_t j : g.pairs) {
      r2 += rho[static_cast<std::size_t>(j)] * rho[static_cast<std::size_t>(j)];
      g.lo = std::min(g.lo, lambda[static_cast<std::size_t>(j)]);
      g.hi = std::max(g.hi, lambda[static_cast<std::size_t>(j)]);
    }
    g.residual = std::sqrt(r2);
    const Timer gram_timer;
    g.eps = gram_defect(b, sb, n, column, g.pairs, abs_b, gram_width);
    if (opt.diagnostics) opt.diagnostics->gram_s += gram_timer.seconds();
    if (!(g.eps < kMaxOrthogonalityDefect)) {
      g.eta = kInfinity;
      return;
    }
    const double inv = 1.0 / std::sqrt(1.0 - g.eps);
    g.eta = (g.residual * inv + std::sqrt(1.0 + g.eps) * (g.hi - g.lo) * (inv - 1.0)) * (1.0 + 4.0 * kRoundoff);
  };

  std::vector<char> placed(static_cast<std::size_t>(m + e), 0);
  for (const CertifiedWindow& win : windows) {
    std::vector<index_t> in;
    for (index_t j = 0; j < m + e; ++j) {
      const double l = lambda[static_cast<std::size_t>(j)];
      if (!placed[static_cast<std::size_t>(j)] && l >= win.lower && l < win.upper) in.push_back(j);
    }
    if (in.empty()) continue;
    for (index_t j : in) placed[static_cast<std::size_t>(j)] = 1;
    std::sort(in.begin(), in.end(), [&](index_t i, index_t j) {
      return lambda[static_cast<std::size_t>(i)] < lambda[static_cast<std::size_t>(j)];
    });
    const auto count = static_cast<index_t>(in.size());
    const std::string range = "[" + std::to_string(win.lower) + ", " + std::to_string(win.upper) + ")";
    if (count > win.count) {
      issues.push_back(std::to_string(count) + " pairs in the window " + range + " of " + std::to_string(win.count) +
                       " eigenvalues");
      continue;
    }
    // The window's whole spectral subspace: one group, gap = distance to the window ends.
    const auto window_group = [&]() {
      Group g;
      g.pairs = in;
      measure(g);
      describe(g, std::min(g.lo - win.lower, win.upper - g.hi), "window", win.lower, win.upper, win.count);
    };
    if (count < win.count) {
      window_group();
      continue;
    }
    // As many pairs as eigenvalues: clusters with disjoint Kahan intervals inside the window.
    std::vector<Group> groups;
    for (std::size_t q = 0; q < in.size(); ++q) {
      const index_t j = in[q];
      const double l = lambda[static_cast<std::size_t>(j)];
      bool join = false;
      if (!groups.empty()) {
        const index_t prev = groups.back().pairs.back();
        const double lp = lambda[static_cast<std::size_t>(prev)];
        const double close = opt.cluster_rtol * (std::max(std::abs(l), std::abs(lp)) + opt.scale);
        join = l - lp <= close || l - lp <= rho[static_cast<std::size_t>(j)] + rho[static_cast<std::size_t>(prev)];
      }
      if (join)
        groups.back().pairs.push_back(j);
      else
        groups.push_back(Group{{j}});
    }
    for (Group& g : groups) measure(g);
    for (;;) {  // merge neighbours whose intervals meet (each merge shortens the list)
      std::size_t meet = groups.size();
      for (std::size_t q = 0; q + 1 < groups.size(); ++q)
        if (groups[q].hi + groups[q].eta >= groups[q + 1].lo - groups[q + 1].eta) {
          meet = q;
          break;
        }
      if (meet == groups.size()) break;
      groups[meet].pairs.insert(groups[meet].pairs.end(), groups[meet + 1].pairs.begin(),
                                groups[meet + 1].pairs.end());
      groups.erase(groups.begin() + static_cast<std::ptrdiff_t>(meet) + 1);
      measure(groups[meet]);
    }
    const bool inside = std::isfinite(groups.front().eta) &&
                        groups.front().lo - groups.front().eta > win.lower &&
                        groups.back().hi + groups.back().eta < win.upper;
    if (!inside) {  // an interval reaches a window end (or a group is not independent)
      window_group();
      continue;
    }
    for (std::size_t q = 0; q < groups.size(); ++q) {
      const Group& g = groups[q];
      double gap = std::min(g.lo - win.lower, win.upper - g.hi);
      if (q > 0) gap = std::min(gap, g.lo - (groups[q - 1].hi + groups[q - 1].eta));
      if (q + 1 < groups.size()) gap = std::min(gap, groups[q + 1].lo - groups[q + 1].eta - g.hi);
      describe(g, gap, "cluster", g.lo - g.eta, g.hi + g.eta, static_cast<index_t>(g.pairs.size()));
    }
  }
  index_t without = 0;
  double worst = 0.0;
  for (index_t j = 0; j < m; ++j) {
    const double v = per_pair[static_cast<std::size_t>(j)];
    if (std::isnan(v))
      ++without;
    else
      worst = std::max(worst, v);
  }
  if (without > 0) {
    issues.insert(issues.begin(), std::to_string(without) + " of " + std::to_string(m) +
                                      " pair(s) without a bound (outside the certified windows, no gap, or "
                                      "vectors not numerically independent)");
  } else {
    rep.max_sin_bound = worst;
  }
  for (const std::string& s : issues) rep.note += (rep.note.empty() ? "" : "; ") + s;
  return rep;
}

namespace {

template <class T>
bool diagonal_matrix(const CsrMatrix<T>& b) {
  for (index_t i = 0; i < b.nrows; ++i)
    for (index_t p = b.rowptr[i]; p < b.rowptr[i + 1]; ++p)
      if (b.colind[p] != i) return false;
  return true;
}

/// Smallest diagonal entry of B (its real part; 0 when one is not positive).
template <class T>
double min_diagonal(const CsrMatrix<T>& b) {
  double dmin = kInfinity;
  for (const double inv : inverse_diagonal(b)) dmin = std::min(dmin, std::isfinite(inv) ? 1.0 / inv : 0.0);
  return dmin;
}

/// lambda_min(B) and lambda_min(S), S = D^{-1/2} B D^{-1/2}, for the B^{-1}-norms (B HPD): a proof
/// where one is cheap - the diagonal of a diagonal B, Gershgorin, the definiteness proof the solve
/// made (Ctx::b_scaled_lower), the incomplete-Cholesky proof of norms.hpp within half the solve's
/// mean factorization time (at least 0.05 s) - else, with subspace_bound = on, an inertia count of
/// B - mu D (one or two more factorizations of B's pattern), and otherwise an estimate (not proven;
/// never above a mu at which a count found lambda_min(S) <= mu; BMinBound::note says why).
template <class T>
BMinBound b_min_bound(Ctx& c, const CsrMatrix<T>& b, bool diagonal) {
  BMinBound r;
  const double dmin = min_diagonal(b);
  if (diagonal) {
    r.value = dmin;
    r.proven = dmin > 0.0 && std::isfinite(dmin);
    r.source = "diagonal";
    r.scaled = 1.0;  // S = I
    return r;
  }
  // lambda_min(S) >= lower (norms.hpp: S = D^{-1/2} B D^{-1/2}) gives lambda_min(B) >= lower min_i b_ii;
  // the factor 1 - 8u covers the rounding of the scaled entries the proofs work with.
  const auto scaled_of = [](double lower) { return lower * (1.0 - 8.0 * kRoundoff); };
  const double from_solve = c.b_scaled_lower > 0.0 && dmin > 0.0 ? scaled_of(c.b_scaled_lower) : 0.0;
  const GershgorinBounds g = gershgorin_bounds(b);
  if (g.plain > 0.0 || g.scaled > 0.0) {
    r.scaled = std::max(std::max(g.scaled, from_solve), 0.0);
    r.value = std::max(g.plain, r.scaled * dmin * (1.0 - 4.0 * kRoundoff));
    r.source = "gershgorin";
    return r;
  }
  if (from_solve > 0.0) {
    r.scaled = from_solve;
    r.value = from_solve * dmin * (1.0 - 4.0 * kRoundoff);
    r.source = "incomplete_cholesky";
    return r;
  }
  // The incomplete-Cholesky proof, unless the solve's own attempt already settled it (the same
  // Lanczos seed gives the same estimate theta, and a failure that is not a budget limit repeats).
  HpdProof proof;
  if (c.b_proof_settled) {
    proof.theta_min = c.b_theta_min;
    proof.outcome = "settled by the solve's proof";
  } else {
    const FactorStats& fs = c.rep.factor_stats;
    const double t_factor = fs.factorizations > 0 ? fs.factorize_s / static_cast<double>(fs.factorizations) : 0.0;
    HpdProofOptions po;
    po.max_seconds = std::max(0.5 * t_factor, 0.05);
    po.max_bytes = std::max(0.0, 0.5 * budget_left(c));
    po.seed = c.cfg.seed;
    proof = prove_positive_definite(b, po);
    event(c, "subspace_b_min", {{"proven", proof.proven}, {"outcome", proof.outcome}, {"lower", proof.lower_bound},
                                {"theta_min", proof.theta_min}, {"seconds", proof.seconds},
                                {"budget_s", po.max_seconds}});
  }
  if (proof.proven && dmin > 0.0) {
    r.scaled = scaled_of(proof.lower_bound);
    r.value = r.scaled * dmin * (1.0 - 4.0 * kRoundoff);
    r.source = "incomplete_cholesky";
    return r;
  }
  // An inertia count: B - mu D has the inertia of S - mu I (Sylvester), so an LDL^T factorization
  // of it without negative and zero pivots proves lambda_min(S) > mu - the counting argument of the
  // completeness certificate (compute_inertia: own analysis, double precision, no BLR, factors
  // discarded). mu = theta_min / 2 (the Lanczos estimate, from inside), then theta_min / 20. The
  // assembly rounds the diagonal (1 - mu) b_ii by at most 4u b_ii: lambda_min(S) > mu - 4u. A
  // count with a negative or zero pivot shows lambda_min(S) <= mu instead (below).
  double below = kInfinity;
  std::string counted;  // the counts that did not prove it
  if (c.cfg.subspace_bound == Toggle::On && !(proof.theta_min > 0.0 && dmin > 0.0)) {
    r.note = "no inertia count: no positive Lanczos estimate of lambda_min(D^{-1/2} B D^{-1/2}) to place its shift";
  } else if (c.cfg.subspace_bound == Toggle::On) {
    CsrMatrix<T> diag = identity<T>(b.nrows);
    const std::vector<double> inv = inverse_diagonal(b);
    for (index_t i = 0; i < b.nrows; ++i)
      diag.values[static_cast<std::size_t>(i)] = T(1.0 / inv[static_cast<std::size_t>(i)]);
    const ShiftedPencil<T> pencil(diag, &b);
    const FactorOptions fo = factor_options_from(c.cfg, count_allowance_mb(c, 0.0));
    for (const double share : {0.5, 0.05}) {
      const double mu = share * proof.theta_min;
      const Timer timer;
      Inertia in;
      std::string error;
      try {
        in = compute_inertia(pencil, -mu, 1.0, fo);
      } catch (const Error& e) {
        error = e.what();
      } catch (const std::bad_alloc&) {
        error = "allocation failure (std::bad_alloc)";
      }
      const bool proven = error.empty() && in.valid && in.neg == 0 && in.zero == 0;
      event(c, "subspace_b_inertia", {{"mu", mu}, {"proven", proven}, {"valid", in.valid},
                                      {"neg", static_cast<std::int64_t>(in.neg)},
                                      {"zero", static_cast<std::int64_t>(in.zero)}, {"seconds", timer.seconds()},
                                      {"error", error}});
      if (proven) {
        r.scaled = (mu - 4.0 * kRoundoff) * (1.0 - 4.0 * kRoundoff);
        r.value = r.scaled * dmin * (1.0 - 4.0 * kRoundoff);
        r.source = "inertia_count";
        return r;
      }
      if (!error.empty()) {  // no memory or no factorization: a smaller mu does not help
        r.note = "the inertia count of B - mu diag(B) at mu = " + fmt(mu) + " failed: " + error;
        break;
      }
      // Counted, but S - mu I has a negative or zero pivot or is singular (compute_inertia: valid
      // false): lambda_min(S) <= mu (up to the 4u of the assembly), so no estimate may exceed mu.
      below = std::min(below, mu);
      counted += std::string(counted.empty() ? "" : ", ") + std::to_string(in.neg) + " negative and " +
                 std::to_string(in.zero) + " zero pivot(s)" + (in.valid ? "" : " (singular)") + " at mu = " + fmt(mu);
    }
    if (!counted.empty())
      r.note = "the inertia counts of B - mu diag(B) found " + counted + ": lambda_min(D^{-1/2} B D^{-1/2}) <= " +
               fmt(below) + (r.note.empty() ? "" : "; " + r.note);
  }
  // Not proven: half the Lanczos estimate (from inside) of lambda_min of S, or half the smallest
  // mu a count showed to be above it, times its smallest diagonal entry for B; or half the
  // estimate of lambda_min(B) itself.
  r.scaled = proof.theta_min > 0.0 && dmin > 0.0 ? 0.5 * std::min(proof.theta_min, below) : 0.0;
  double estimate = r.scaled * dmin;
  if (!(estimate > 0.0)) estimate = 0.5 * estimate_norm2(b, 30, c.cfg.seed).ritz_min;
  r.value = estimate > 0.0 ? estimate : std::numeric_limits<double>::min();
  r.proven = false;
  r.source = "estimate";
  return r;
}

}  // namespace

template <class T>
void attach_subspace_bound(Ctx& c, const CsrMatrix<T>& a, const CsrMatrix<T>* b, const Solution<T>& sol) {
  PhaseScope phase(c.clock, Phase::Verify);
  const Timer timer;
  SolveReport& rep = c.rep;
  SubspaceReport& out = rep.subspace;
  out = SubspaceReport{};
  SubspaceDiagnostics diag;
  const InertiaCertificate& cert = rep.certificate;
  if (c.cfg.subspace_bound == Toggle::Off) {
    out.note = "disabled by configuration";
  } else if (rep.problem == ProblemType::GeneralizedIndefinite) {
    out.note = "not available for indefinite B (no completeness certificate)";
  } else if (!cert.performed) {
    out.note = "no completeness certificate" + (cert.note.empty() ? std::string() : " (" + cert.note + ")");
  } else if (!cert.passed) {
    out.note = "the completeness certificate did not pass";
  } else if (c.certified.empty()) {
    out.note = "no certified window";
  } else {
    SubspaceOptions opt;
    opt.scale = rep.scale;
    opt.diagnostics = &diag;
    opt.memory_bytes = std::max(0.0, 0.9 * budget_left(c));
    try {
      if (b) {
        opt.b_diagonal = diagonal_matrix(*b);
        opt.b_min = b_min_bound(c, *b, opt.b_diagonal);
      }
      std::vector<double> per_pair;
      out = subspace_bounds(a, b, sol.eigenvalues, sol.eigenvectors, c.unreturned_lambda, unreturned_vectors<T>(c),
                            c.certified, opt, per_pair);
      for (std::size_t j = 0; j < per_pair.size() && j < rep.pairs.size(); ++j)
        rep.pairs[j].subspace_sin_bound = per_pair[j];
      out.rigorous = out.rigorous && cert.rigorous;
      out.failure_probability = cert.failure_probability;
      if (b && !opt.b_min.proven) {
        const std::string why =
            "lambda_min(B) is estimated, not proven: the B^{-1}-norm remainder and rounding terms rest on that "
            "estimate (" +
            (c.cfg.subspace_bound == Toggle::On ? opt.b_min.note
                                                : "subspace_bound = on tries to prove it by an inertia count of B - "
                                                  "mu diag(B)") +
            ")";
        out.note = out.note.empty() ? why : why + "; " + out.note;
      }
    } catch (const Error& e) {
      if (e.code() != Error::Code::OutOfMemoryBudget) throw;
      out = SubspaceReport{};
      out.note = std::string("not computed: ") + e.what();
    } catch (const std::bad_alloc&) {
      out = SubspaceReport{};
      out.note = "not computed: allocation failure (std::bad_alloc)";
    }
  }
  out.seconds = timer.seconds();
  event(c, "subspace_bound", {{"performed", out.performed}, {"max_sin_bound", out.max_sin_bound},
                              {"rigorous", out.rigorous}, {"groups", static_cast<std::int64_t>(out.groups.size())},
                              {"b_min_source", out.b_min_source}, {"seconds", out.seconds},
                              {"residual_s", diag.residual_s}, {"cg_s", diag.cg_s},
                              {"cg_iterations", static_cast<std::int64_t>(diag.cg_iterations)},
                              {"gram_s", diag.gram_s}, {"note", out.note}});
}

#define HS_INSTANTIATE_SUBSPACE(T)                                                                          \
  template SubspaceReport subspace_bounds<T>(const CsrMatrix<T>&, const CsrMatrix<T>*, const std::vector<double>&, \
                                             const DenseMatrix<T>&, const std::vector<double>&,                  \
                                             const DenseMatrix<T>&, const std::vector<CertifiedWindow>&,         \
                                             const SubspaceOptions&, std::vector<double>&);                      \
  template std::vector<double> residual_b_inverse_norms<T>(const CsrMatrix<T>&, const CsrMatrix<T>*,               \
                                                           const std::vector<double>&, const DenseMatrix<T>&,     \
                                                           const SubspaceOptions&, std::vector<double>*);         \
  template GershgorinBounds gershgorin_bounds<T>(const CsrMatrix<T>&);                                 \
  template double gershgorin_lambda_min<T>(const CsrMatrix<T>&);                                       \
  template void attach_subspace_bound<T>(Ctx&, const CsrMatrix<T>&, const CsrMatrix<T>*, const Solution<T>&);
HS_FOR_EACH_SCALAR(HS_INSTANTIATE_SUBSPACE)
#undef HS_INSTANTIATE_SUBSPACE

}  // namespace hs::driver
