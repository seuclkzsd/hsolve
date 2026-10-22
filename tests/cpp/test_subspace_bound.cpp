// Eigenvector subspace-angle bounds (src/driver/subspace.hpp, SolveReport::subspace; DESIGN §3.6-8c).
// Small dense problems with exactly known eigenvectors: A = W^H diag(lambda) W, B = W^H W, so that the
// B-orthonormal eigenvectors are V = W^{-1} and W maps the B geometry to the Euclidean one with the
// exact eigenvectors on the unit vectors. The bound must hold for the true angles and stay within
// three orders of magnitude of them; multiplicities, unreturned copies, GHEP with diagonal and
// general B, and the end-to-end report.
#include <gtest/gtest.h>

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <limits>
#include <random>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

#include "driver/subspace.hpp"
#include "hsolve/solver.hpp"
#include "hsolve/sparse.hpp"
#include "support/fixtures.hpp"

namespace {

using hs::cplx;
using hs::DenseMatrix;
using hs::index_t;

template <class T>
T random_entry(std::mt19937_64& g) {
  std::uniform_real_distribution<double> u(-1.0, 1.0);
  if constexpr (hs::is_complex_v<T>) {
    const double re = u(g);
    return T(re, u(g));
  } else {
    return u(g);
  }
}

template <class T>
T conj_of(T v) {
  if constexpr (hs::is_complex_v<T>)
    return std::conj(v);
  else
    return v;
}

template <class T>
DenseMatrix<T> multiply(const DenseMatrix<T>& a, const DenseMatrix<T>& b, bool adjoint_a = false) {
  const index_t m = adjoint_a ? a.cols() : a.rows(), k = adjoint_a ? a.rows() : a.cols(), n = b.cols();
  DenseMatrix<T> c(m, n);
  for (index_t j = 0; j < n; ++j)
    for (index_t p = 0; p < k; ++p)
      for (index_t i = 0; i < m; ++i) c(i, j) += (adjoint_a ? conj_of(a(p, i)) : a(i, p)) * b(p, j);
  return c;
}

// Orthonormal columns by modified Gram-Schmidt, twice (columns assumed independent).
template <class T>
void orthonormalize(DenseMatrix<T>& q) {
  const index_t n = q.rows(), m = q.cols();
  for (int pass = 0; pass < 2; ++pass)
    for (index_t j = 0; j < m; ++j) {
      for (index_t i = 0; i < j; ++i) {
        T d = 0;
        for (index_t r = 0; r < n; ++r) d += conj_of(q(r, i)) * q(r, j);
        for (index_t r = 0; r < n; ++r) q(r, j) -= d * q(r, i);
      }
      double s = 0;
      for (index_t r = 0; r < n; ++r) s += std::norm(q(r, j));
      for (index_t r = 0; r < n; ++r) q(r, j) /= std::sqrt(s);
    }
}

template <class T>
DenseMatrix<T> random_unitary(index_t n, std::mt19937_64& g) {
  DenseMatrix<T> q(n, n);
  for (index_t j = 0; j < n; ++j)
    for (index_t i = 0; i < n; ++i) q(i, j) = random_entry<T>(g);
  orthonormalize(q);
  return q;
}

enum class BKind { Identity, Diagonal, General };

template <class T>
struct Exact {
  hs::CsrMatrix<T> a, b;
  bool has_b = false;
  DenseMatrix<T> v;  // B-orthonormal eigenvectors (columns)
  DenseMatrix<T> w;  // V^{-1}
  std::vector<double> lambda;
};

// A = W^H diag(lambda) W, B = W^H W with W = U diag(s) Q^H (identity: s = 1, U = I; diagonal:
// Q = I, U = I, s = sqrt(d)); V = W^{-1} = Q diag(1/s) U^H.
template <class T>
Exact<T> exact_problem(const std::vector<double>& lambda, BKind kind, std::uint64_t seed) {
  std::mt19937_64 g(seed);
  const auto n = static_cast<index_t>(lambda.size());
  const DenseMatrix<T> q = random_unitary<T>(n, g);
  DenseMatrix<T> u(n, n);
  std::vector<double> s(static_cast<std::size_t>(n), 1.0);
  std::uniform_real_distribution<double> spread(0.5, 2.0);
  if (kind == BKind::General) {
    u = random_unitary<T>(n, g);
    for (double& x : s) x = spread(g);
  } else {
    for (index_t i = 0; i < n; ++i) u(i, i) = 1.0;
    if (kind == BKind::Diagonal)
      for (double& x : s) x = std::sqrt(spread(g));
  }
  Exact<T> e;
  e.lambda = lambda;
  e.has_b = kind != BKind::Identity;
  // Diagonal B: W = diag(s) Q^H gives B = W^H W = Q diag(s^2) Q^H - not diagonal; instead take
  // W = Q diag(s): B = diag(s^2), V = diag(1/s) Q^H.
  DenseMatrix<T> w(n, n), v(n, n);
  for (index_t i = 0; i < n; ++i)
    for (index_t j = 0; j < n; ++j) {
      T wij = 0, vij = 0;
      if (kind == BKind::Diagonal) {
        wij = q(i, j) * s[static_cast<std::size_t>(j)];
        vij = conj_of(q(j, i)) / s[static_cast<std::size_t>(i)];
      } else {
        for (index_t p = 0; p < n; ++p) {
          wij += u(i, p) * s[static_cast<std::size_t>(p)] * conj_of(q(j, p));
          vij += q(i, p) / s[static_cast<std::size_t>(p)] * conj_of(u(j, p));
        }
      }
      w(i, j) = wij;
      v(i, j) = vij;
    }
  DenseMatrix<T> lw(n, n);
  for (index_t j = 0; j < n; ++j)
    for (index_t i = 0; i < n; ++i) lw(i, j) = lambda[static_cast<std::size_t>(i)] * w(i, j);
  DenseMatrix<T> a = multiply(w, lw, true), b = multiply(w, w, true);
  // Exactly Hermitian storage.
  for (index_t j = 0; j < n; ++j)
    for (index_t i = 0; i < j; ++i) {
      a(i, j) = conj_of(a(j, i));
      b(i, j) = conj_of(b(j, i));
    }
  for (index_t i = 0; i < n; ++i) {
    a(i, i) = std::real(a(i, i));
    b(i, i) = std::real(b(i, i));
  }
  e.a = hs::test::from_dense(a);
  if (e.has_b) e.b = hs::test::from_dense(b, kind == BKind::Diagonal ? 1e-14 : 0.0);
  e.v = std::move(v);
  e.w = std::move(w);
  return e;
}

// ||sin Theta||_F between span(x) (columns, B geometry) and the exact eigenvectors `exact`
// (indices into lambda): W x in Euclidean coordinates, orthonormalized; the mass outside the rows
// `exact`.
template <class T>
double true_sin(const Exact<T>& e, const DenseMatrix<T>& x, const std::vector<index_t>& exact) {
  DenseMatrix<T> z = multiply(e.w, x);
  orthonormalize(z);
  std::vector<char> in(static_cast<std::size_t>(z.rows()), 0);
  for (index_t i : exact) in[static_cast<std::size_t>(i)] = 1;
  double s = 0;
  for (index_t j = 0; j < z.cols(); ++j)
    for (index_t i = 0; i < z.rows(); ++i)
      if (!in[static_cast<std::size_t>(i)]) s += std::norm(z(i, j));
  return std::sqrt(s);
}

template <class T>
DenseMatrix<T> columns(const DenseMatrix<T>& x, const std::vector<index_t>& cols) {
  DenseMatrix<T> out(x.rows(), static_cast<index_t>(cols.size()));
  for (std::size_t c = 0; c < cols.size(); ++c)
    for (index_t i = 0; i < x.rows(); ++i) out(i, static_cast<index_t>(c)) = x(i, cols[c]);
  return out;
}

// Perturbed exact eigenvectors (relative size eps), B-normalized, with their Rayleigh quotients.
template <class T>
void perturbed_pairs(const Exact<T>& e, const std::vector<index_t>& idx, double eps, std::uint64_t seed,
                     DenseMatrix<T>& x, std::vector<double>& theta) {
  std::mt19937_64 g(seed);
  const index_t n = e.v.rows();
  x = columns(e.v, idx);
  for (index_t j = 0; j < x.cols(); ++j) {
    double vn = 0;
    for (index_t i = 0; i < n; ++i) vn += std::norm(x(i, j));
    for (index_t i = 0; i < n; ++i) x(i, j) += eps * std::sqrt(vn / static_cast<double>(n)) * random_entry<T>(g);
  }
  theta.clear();
  const DenseMatrix<T> ad = hs::test::to_dense(e.a);
  const DenseMatrix<T> bd = e.has_b ? hs::test::to_dense(e.b) : DenseMatrix<T>{};
  for (index_t j = 0; j < x.cols(); ++j) {
    T xax = 0, xbx = 0;
    for (index_t i = 0; i < n; ++i) {
      T ai = 0, bi = 0;
      for (index_t p = 0; p < n; ++p) {
        ai += ad(i, p) * x(p, j);
        bi += e.has_b ? bd(i, p) * x(p, j) : (i == p ? x(p, j) : T(0));
      }
      xax += conj_of(x(i, j)) * ai;
      xbx += conj_of(x(i, j)) * bi;
    }
    theta.push_back(std::real(xax) / std::real(xbx));
    for (index_t i = 0; i < n; ++i) x(i, j) /= std::sqrt(std::real(xbx));
  }
}

// Spectrum with a triple and a double eigenvalue inside [0, 2.6), three eigenvalues in [-3.5, -0.5);
// the outer eigenvalues are not equally spaced (on a lattice of equal gaps, which the 36-step Lanczos
// estimate of this small problem resolves exactly, count interpolation lands on eigenvalues).
std::vector<double> spectrum() {
  std::vector<double> l{-3.0, -2.0, -1.2, 0.5, 0.5, 0.5, 1.4, 2.0, 2.0, 3.3};
  for (int i = 0; i < 15; ++i) l.push_back(4.0 + 0.37 * i + 0.019 * i * i);
  for (int i = 0; i < 11; ++i) l.push_back(-4.0 - 0.41 * i - 0.023 * i * i);
  return l;
}

std::vector<index_t> exact_in(const std::vector<double>& lambda, double lo, double hi) {
  std::vector<index_t> out;
  for (std::size_t i = 0; i < lambda.size(); ++i)
    if (lambda[i] >= lo && lambda[i] <= hi) out.push_back(static_cast<index_t>(i));
  return out;
}

template <class T>
hs::driver::SubspaceOptions options(const Exact<T>& e, BKind kind) {
  hs::driver::SubspaceOptions opt;
  opt.scale = 10.0;
  opt.b_diagonal = kind == BKind::Diagonal;
  if (e.has_b) {
    const auto wb = hs::test::dense_eigenvalues(e.b, static_cast<const hs::CsrMatrix<T>*>(nullptr));
    opt.b_min = {wb.front() * (1.0 - 1e-8), true, "test"};
  }
  return opt;
}

// Every group: the bound holds for the true angle of its returned vectors against the exact
// eigenvectors of [lower, upper] and is at most `orders` decades above it.
template <class T>
void expect_bounds(const Exact<T>& e, const DenseMatrix<T>& x, const hs::SubspaceReport& rep, double orders) {
  ASSERT_TRUE(rep.performed);
  for (const auto& g : rep.groups) {
    const auto exact = exact_in(e.lambda, g.lower, g.upper);
    EXPECT_EQ(static_cast<index_t>(exact.size()), g.dimension) << g.kind << " [" << g.lower << ", " << g.upper << "]";
    const double truth = true_sin(e, columns(x, g.pairs), exact);
    EXPECT_LE(truth, g.sin_bound * (1.0 + 1e-8) + 1e-15) << g.kind << " [" << g.lower << ", " << g.upper << "]";
    EXPECT_LE(g.sin_bound, std::pow(10.0, orders) * truth) << g.kind << " [" << g.lower << ", " << g.upper << "]";
  }
}

template <class T>
class SubspaceBoundCore : public ::testing::Test {};
using Scalars = ::testing::Types<double, cplx>;
TYPED_TEST_SUITE(SubspaceBoundCore, Scalars);

TYPED_TEST(SubspaceBoundCore, ClustersOfMultipleEigenvaluesAreBoundedTightly) {
  using T = TypeParam;
  for (const BKind kind : {BKind::Identity, BKind::Diagonal, BKind::General}) {
    const auto e = exact_problem<T>(spectrum(), kind, 7 + static_cast<int>(kind));
    const auto idx = exact_in(e.lambda, 0.0, 2.6);  // 0.5 (x3), 1.4, 2.0 (x2)
    ASSERT_EQ(idx.size(), 6u);
    DenseMatrix<T> x;
    std::vector<double> theta;
    perturbed_pairs(e, idx, 1e-7, 11, x, theta);
    std::vector<double> per_pair;
    const auto rep = hs::driver::subspace_bounds(e.a, e.has_b ? &e.b : nullptr, theta, x, {}, DenseMatrix<T>{},
                                                 {{0.0, 2.6, 6}}, options(e, kind), per_pair);
    ASSERT_EQ(rep.groups.size(), 3u) << rep.note;
    std::vector<index_t> dims;
    for (const auto& g : rep.groups) {
      EXPECT_EQ(g.kind, "cluster");
      dims.push_back(g.dimension);
    }
    EXPECT_EQ(dims, (std::vector<index_t>{3, 1, 2}));
    expect_bounds(e, x, rep, 3.0);
    EXPECT_TRUE(std::isfinite(rep.max_sin_bound));
    EXPECT_LT(rep.max_sin_bound, 1e-4);
    EXPECT_EQ(rep.rigorous, true);
    for (std::size_t j = 0; j < per_pair.size(); ++j) EXPECT_LE(per_pair[j], rep.max_sin_bound);
    EXPECT_EQ(rep.residual_norm, kind == BKind::Identity   ? "2"
                                 : kind == BKind::Diagonal ? "b_inverse_diagonal"
                                                           : "b_inverse_cg");
  }
}

// The scalar steps are one-sided: checked in extended precision, every cluster interval contains
// [min theta - eta, max theta + eta] for the reported residual and orthogonality, every gap is at
// most the distances it is taken from (window ends, neighbouring intervals), and sin_bound is at
// least residual / (gap sqrt(1 - orthogonality)). With exact eigenvectors eta is at rounding level,
// where an interval end rounded to nearest falls short of it in about half the cases.
TYPED_TEST(SubspaceBoundCore, IntervalsGapsAndBoundsAreRoundedOutward) {
  using T = TypeParam;
  using ld = long double;
  static_assert(std::numeric_limits<ld>::digits > std::numeric_limits<double>::digits, "needs extended precision");
  for (const BKind kind : {BKind::Identity, BKind::Diagonal, BKind::General}) {
    const auto e = exact_problem<T>(spectrum(), kind, 31 + static_cast<int>(kind));
    const auto idx = exact_in(e.lambda, 0.0, 2.6);
    DenseMatrix<T> x;
    std::vector<double> theta;
    perturbed_pairs(e, idx, 0.0, 3, x, theta);
    const hs::driver::CertifiedWindow win{0.0, 2.6, 6};
    std::vector<double> per_pair;
    const auto rep = hs::driver::subspace_bounds(e.a, e.has_b ? &e.b : nullptr, theta, x, {}, DenseMatrix<T>{},
                                                 {win}, options(e, kind), per_pair);
    ASSERT_EQ(rep.groups.size(), 3u) << rep.note;
    for (std::size_t q = 0; q < rep.groups.size(); ++q) {
      const auto& g = rep.groups[q];
      ASSERT_EQ(g.kind, "cluster");
      ld lo = std::numeric_limits<ld>::infinity(), hi = -lo;
      for (index_t j : g.pairs) {
        lo = std::min<ld>(lo, theta[static_cast<std::size_t>(j)]);
        hi = std::max<ld>(hi, theta[static_cast<std::size_t>(j)]);
      }
      const ld eps = g.orthogonality, s = std::sqrt(1.0L - eps);
      const ld eta = static_cast<ld>(g.residual) / s + std::sqrt(1.0L + eps) * (hi - lo) * eps / (s * (1.0L + s));
      EXPECT_GE(static_cast<ld>(g.upper) - hi, eta) << q;
      EXPECT_GE(lo - static_cast<ld>(g.lower), eta) << q;
      ld gap = std::min(lo - static_cast<ld>(win.lower), static_cast<ld>(win.upper) - hi);
      if (q > 0) gap = std::min(gap, lo - static_cast<ld>(rep.groups[q - 1].upper));
      if (q + 1 < rep.groups.size()) gap = std::min(gap, static_cast<ld>(rep.groups[q + 1].lower) - hi);
      EXPECT_GT(g.gap, 0.0);
      EXPECT_LE(static_cast<ld>(g.gap), gap) << q;
      EXPECT_GE(static_cast<ld>(g.sin_bound),
                std::min(1.0L, static_cast<ld>(g.residual) / (static_cast<ld>(g.gap) * s)))
          << q;
    }
  }
}

TYPED_TEST(SubspaceBoundCore, TwoWindowsAndAPairOutsideBoth) {
  using T = TypeParam;
  const auto e = exact_problem<T>(spectrum(), BKind::Identity, 21);
  auto idx = exact_in(e.lambda, -3.5, 2.6);  // 3 + 6 pairs
  idx.push_back(9);                          // 3.3: in no window
  DenseMatrix<T> x;
  std::vector<double> theta;
  perturbed_pairs(e, idx, 1e-8, 5, x, theta);
  std::vector<double> per_pair;
  const auto rep = hs::driver::subspace_bounds(e.a, static_cast<const hs::CsrMatrix<T>*>(nullptr), theta, x, {},
                                               DenseMatrix<T>{}, {{-3.5, -0.5, 3}, {0.0, 2.6, 6}},
                                               options(e, BKind::Identity), per_pair);
  EXPECT_EQ(rep.groups.size(), 6u);
  expect_bounds(e, x, rep, 3.0);
  EXPECT_TRUE(std::isnan(per_pair.back()));
  EXPECT_TRUE(std::isnan(rep.max_sin_bound));
  EXPECT_NE(rep.note.find("1 of 10 pair(s) without a bound"), std::string::npos) << rep.note;
}

TYPED_TEST(SubspaceBoundCore, FewerPairsThanEigenvaluesBoundTheWindowOrUseTheUnreturnedCopies) {
  using T = TypeParam;
  const auto e = exact_problem<T>(spectrum(), BKind::General, 3);
  const auto all = exact_in(e.lambda, 0.0, 2.6);
  const std::vector<index_t> kept(all.begin(), all.end() - 1);  // one copy of 2.0 left out
  DenseMatrix<T> x, x_all;
  std::vector<double> theta, theta_all;
  perturbed_pairs(e, all, 1e-7, 17, x_all, theta_all);
  x = columns(x_all, {0, 1, 2, 3, 4});
  theta.assign(theta_all.begin(), theta_all.end() - 1);
  const auto opt = options(e, BKind::General);
  std::vector<double> per_pair;
  // Without the unreturned copy the window's whole spectral subspace is the reference.
  auto rep = hs::driver::subspace_bounds(e.a, &e.b, theta, x, {}, DenseMatrix<T>{}, {{0.0, 2.6, 6}}, opt, per_pair);
  ASSERT_EQ(rep.groups.size(), 1u);
  EXPECT_EQ(rep.groups[0].kind, "window");
  EXPECT_EQ(rep.groups[0].dimension, 6);
  expect_bounds(e, x, rep, 3.0);
  // With it, clusters again: the 2.0 group holds one returned and one unreturned copy.
  const DenseMatrix<T> extra = columns(x_all, {5});
  rep = hs::driver::subspace_bounds(e.a, &e.b, theta, x, {theta_all.back()}, extra, {{0.0, 2.6, 6}}, opt, per_pair);
  ASSERT_EQ(rep.groups.size(), 3u);
  EXPECT_EQ(rep.groups[2].unreturned, 1);
  EXPECT_EQ(rep.groups[2].dimension, 2);
  EXPECT_EQ(rep.groups[2].pairs, (std::vector<index_t>{4}));
  expect_bounds(e, x, rep, 3.0);
  EXPECT_TRUE(std::isfinite(rep.max_sin_bound));
}

TYPED_TEST(SubspaceBoundCore, ResidualNormsBoundTheBInverseNorm) {
  using T = TypeParam;
  for (const BKind kind : {BKind::Diagonal, BKind::General}) {
    const auto e = exact_problem<T>(spectrum(), kind, 31);
    DenseMatrix<T> x;
    std::vector<double> theta;
    perturbed_pairs(e, exact_in(e.lambda, 0.0, 2.6), 1e-5, 2, x, theta);
    const auto rho = hs::driver::residual_b_inverse_norms(e.a, &e.b, theta, x, options(e, kind));
    // ||B^{-1/2} r|| = ||W^{-H} r|| = ||(Lambda - theta) W x||: exact by construction.
    const DenseMatrix<T> z = multiply(e.w, x);
    for (index_t j = 0; j < x.cols(); ++j) {
      double s = 0;
      for (index_t i = 0; i < z.rows(); ++i)
        s += std::norm((e.lambda[static_cast<std::size_t>(i)] - theta[static_cast<std::size_t>(j)]) * z(i, j));
      EXPECT_GE(rho[static_cast<std::size_t>(j)], std::sqrt(s) * (1.0 - 1e-6));
      // CG stops once its remainder estimate is 1% of the quadratic form: at most 0.5% above.
      EXPECT_LE(rho[static_cast<std::size_t>(j)], std::sqrt(s) * (1.0 + 5e-3));
    }
  }
}

// A badly scaled pencil (E A E, E B E with E = diag(10^-k), k uniform in [0, 4]) has the same
// eigenvalues and the eigenvectors E^{-1} V, entries up to 1e4, while lambda_min(B) drops to ~1e-9.
// Rounding terms bounded through max row sums times ||x||, and B^{-1}-norms through lambda_min(B)
// alone, grow with the scaling; the componentwise rounding envelope and the Jacobi-weighted
// B^{-1}-norms (lambda_min of D^{-1/2} B D^{-1/2}, unchanged by E) keep the bound within three
// orders of magnitude of the true angle.
TYPED_TEST(SubspaceBoundCore, BadlyScaledBKeepsTheBoundTight) {
  using T = TypeParam;
  auto e = exact_problem<T>(spectrum(), BKind::General, 41);
  const index_t n = e.v.rows();
  std::mt19937_64 g(5);
  std::uniform_real_distribution<double> decades(0.0, 4.0);
  std::vector<double> s(static_cast<std::size_t>(n));
  for (double& v : s) v = std::pow(10.0, -decades(g));
  const auto rescale = [&](hs::CsrMatrix<T>& m) {
    for (index_t i = 0; i < m.nrows; ++i)
      for (index_t p = m.rowptr[i]; p < m.rowptr[i + 1]; ++p)
        m.values[p] *= s[static_cast<std::size_t>(i)] * s[static_cast<std::size_t>(m.colind[p])];
  };
  rescale(e.a);
  rescale(e.b);
  for (index_t j = 0; j < n; ++j)
    for (index_t i = 0; i < n; ++i) {
      e.v(i, j) /= s[static_cast<std::size_t>(i)];  // V -> E^{-1} V
      e.w(i, j) *= s[static_cast<std::size_t>(j)];  // W -> W E (B = (W E)^H (W E))
    }
  DenseMatrix<T> x;
  std::vector<double> theta;
  perturbed_pairs(e, exact_in(e.lambda, 0.0, 2.6), 1e-9, 13, x, theta);
  auto opt = options(e, BKind::General);
  DenseMatrix<T> sd = hs::test::to_dense(e.b);
  std::vector<double> d(static_cast<std::size_t>(n));
  for (index_t i = 0; i < n; ++i) d[static_cast<std::size_t>(i)] = std::real(sd(i, i));
  for (index_t j = 0; j < n; ++j)
    for (index_t i = 0; i < n; ++i)
      sd(i, j) /= std::sqrt(d[static_cast<std::size_t>(i)] * d[static_cast<std::size_t>(j)]);
  const auto ws = hs::test::dense_eigenvalues(hs::test::from_dense(sd), static_cast<const hs::CsrMatrix<T>*>(nullptr));
  opt.b_min.scaled = ws.front() * (1.0 - 1e-8);
  EXPECT_LT(opt.b_min.value, 1e-7);
  std::vector<double> per_pair;
  const auto rep = hs::driver::subspace_bounds(e.a, &e.b, theta, x, {}, DenseMatrix<T>{}, {{0.0, 2.6, 6}}, opt,
                                               per_pair);
  ASSERT_EQ(rep.groups.size(), 3u) << rep.note;
  expect_bounds(e, x, rep, 3.0);
}

TEST(SubspaceBoundGershgorin, ProvesOnlyWhatHolds) {
  // Diagonally dominant: positive and below the true lambda_min.
  const auto b = hs::test::random_hpd<double>(60, 0.05, 4);
  const double g = hs::driver::gershgorin_lambda_min(b);
  const auto wb = hs::test::dense_eigenvalues(b, static_cast<const hs::CsrMatrix<double>*>(nullptr));
  EXPECT_GT(g, 0.0);
  EXPECT_LE(g, wb.front());
  // The Jacobi-scaled bound: lambda_min(S) >= scaled, and lambda_min(B) >= lambda_min(S) min b_ii.
  const auto gb = hs::driver::gershgorin_bounds(b);
  EXPECT_GT(gb.scaled, 0.0);
  EXPECT_LE(gb.scaled * gb.min_diagonal, wb.front());
  EXPECT_LE(gb.plain, wb.front());
  // The 1-D Laplacian (eigenvalues down to ~1e-3, not strictly dominant): no proof.
  EXPECT_EQ(hs::driver::gershgorin_lambda_min(hs::test::laplacian_1d<double>(50)), 0.0);
}

// ---------------------------------------------------------------- end to end (hs::solve)

template <class T>
hs::SolverConfig base_config() {
  hs::SolverConfig c;
  c.threads = 2;
  c.memory_budget_gb = 2;
  c.deterministic = true;
  return c;
}

template <class T>
void expect_solution_bounds(const Exact<T>& e, const hs::Solution<T>& s) {
  const auto& sub = s.report.subspace;
  ASSERT_TRUE(sub.performed) << sub.note;
  ASSERT_TRUE(std::isfinite(sub.max_sin_bound)) << sub.note;
  EXPECT_LT(sub.max_sin_bound, 1e-6);
  EXPECT_TRUE(sub.rigorous);
  EXPECT_EQ(sub.failure_probability, 0.0);
  index_t covered = 0;
  for (const auto& g : sub.groups) {
    covered += static_cast<index_t>(g.pairs.size());
    const auto exact = exact_in(e.lambda, g.lower, g.upper);
    EXPECT_EQ(static_cast<index_t>(exact.size()), g.dimension);
    // The computed vectors are accurate to rounding: compare with a floor for the true angle's own
    // rounding.
    EXPECT_LE(true_sin(e, columns(s.eigenvectors, g.pairs), exact), g.sin_bound + 1e-12);
  }
  EXPECT_EQ(covered, static_cast<index_t>(s.eigenvalues.size()));
  for (const auto& p : s.report.pairs) EXPECT_LE(p.subspace_sin_bound, sub.max_sin_bound);
}

template <class T>
class SubspaceBoundSolve : public ::testing::Test {};
TYPED_TEST_SUITE(SubspaceBoundSolve, Scalars);

TYPED_TEST(SubspaceBoundSolve, NearestWithAMultipleEigenvalueCutByK) {
  using T = TypeParam;
  const auto e = exact_problem<T>(spectrum(), BKind::Identity, 41);
  auto cfg = base_config<T>();
  cfg.target.sigma = 0.6;
  cfg.target.k = 4;  // 0.5 (x3) and 1.4
  auto s = hs::solve(e.a, static_cast<const hs::CsrMatrix<T>*>(nullptr), cfg);
  ASSERT_TRUE(s.report.success) << s.report.to_json();
  expect_solution_bounds(e, s);
  cfg.target.k = 2;  // two of the three copies of 0.5
  s = hs::solve(e.a, static_cast<const hs::CsrMatrix<T>*>(nullptr), cfg);
  ASSERT_TRUE(s.report.success) << s.report.to_json();
  expect_solution_bounds(e, s);
  ASSERT_EQ(s.report.subspace.groups.size(), 1u);
  EXPECT_EQ(s.report.subspace.groups[0].dimension, 3);
}

TYPED_TEST(SubspaceBoundSolve, GeneralizedWindowTargets) {
  using T = TypeParam;
  for (const BKind kind : {BKind::Diagonal, BKind::General}) {
    const auto e = exact_problem<T>(spectrum(), kind, 51 + static_cast<int>(kind));
    auto cfg = base_config<T>();
    cfg.target.mode = hs::TargetMode::Interval;
    cfg.target.lower = -2.5;
    cfg.target.upper = 2.6;
    cfg.slice_size = 3;  // several slices
    auto s = hs::solve(e.a, &e.b, cfg);
    ASSERT_TRUE(s.report.success) << s.report.to_json();
    EXPECT_EQ(s.eigenvalues.size(), 8u);
    expect_solution_bounds(e, s);
    cfg = base_config<T>();
    cfg.target.mode = hs::TargetMode::Smallest;
    cfg.target.k = 5;
    s = hs::solve(e.a, &e.b, cfg);
    ASSERT_TRUE(s.report.success) << s.report.to_json();
    expect_solution_bounds(e, s);
  }
}

TEST(SubspaceBoundSolveReport, NullWithAReasonUnlessACertificatePassed) {
  const auto e = exact_problem<double>(spectrum(), BKind::Identity, 61);
  auto cfg = base_config<double>();
  cfg.target.sigma = 1.3;
  cfg.target.k = 3;
  cfg.certificate = hs::CertificateMode::Off;
  auto s = hs::solve(e.a, static_cast<const hs::CsrMatrix<double>*>(nullptr), cfg);
  EXPECT_FALSE(s.report.subspace.performed);
  EXPECT_NE(s.report.subspace.note.find("no completeness certificate"), std::string::npos);
  auto j = nlohmann::json::parse(s.report.to_json());
  EXPECT_TRUE(j["subspace"]["max_sin_bound"].is_null());
  EXPECT_TRUE(j["pairs"][0]["subspace_sin_bound"].is_null());

  cfg.certificate = hs::CertificateMode::Exact;
  cfg.subspace_bound = hs::Toggle::Off;
  s = hs::solve(e.a, static_cast<const hs::CsrMatrix<double>*>(nullptr), cfg);
  EXPECT_TRUE(s.report.success);
  EXPECT_FALSE(s.report.subspace.performed);
  EXPECT_EQ(s.report.subspace.note, "disabled by configuration");

  cfg.subspace_bound = hs::Toggle::Auto;
  s = hs::solve(e.a, static_cast<const hs::CsrMatrix<double>*>(nullptr), cfg);
  j = nlohmann::json::parse(s.report.to_json());
  for (const char* key : {"performed", "max_sin_bound", "rigorous", "failure_probability", "residual_norm", "b_min",
                          "b_min_source", "groups", "note", "seconds"})
    EXPECT_TRUE(j["subspace"].contains(key)) << key;
  for (const char* key : {"kind", "pairs", "unreturned", "lower", "upper", "dimension", "gap", "residual",
                          "orthogonality", "sin_bound"})
    EXPECT_TRUE(j["subspace"]["groups"][0].contains(key)) << key;
  EXPECT_TRUE(j["subspace"]["max_sin_bound"].is_number());
  EXPECT_TRUE(j["pairs"][0]["subspace_sin_bound"].is_number());
  EXPECT_EQ(j["subspace"]["b_min_source"], "identity");

  // lambda_min(B) of a B that neither Gershgorin nor the incomplete-Cholesky proof covers (the 1-D
  // Laplacian: not strictly dominant, Jacobi-scaled lambda_min ~ 1e-3 < 0.1): estimated by default
  // (rigorous false, the note says how to prove it); with subspace_bound = on an inertia count of
  // B - mu D proves it.
  {
    const index_t n = 60;
    const auto a = hs::identity<double>(n);
    const auto b = hs::test::laplacian_1d<double>(n);
    auto gcfg = base_config<double>();
    gcfg.target.sigma = 1.0;
    gcfg.target.k = 3;
    const auto est = hs::solve(a, &b, gcfg);
    ASSERT_TRUE(est.report.success) << est.report.to_json();
    EXPECT_TRUE(est.report.subspace.performed);
    EXPECT_EQ(est.report.subspace.b_min_source, "estimate");
    EXPECT_FALSE(est.report.subspace.rigorous);
    EXPECT_NE(est.report.subspace.note.find("subspace_bound = on"), std::string::npos) << est.report.subspace.note;
    gcfg.subspace_bound = hs::Toggle::On;
    const auto gs = hs::solve(a, &b, gcfg);
    ASSERT_TRUE(gs.report.success) << gs.report.to_json();
    const auto& sub = gs.report.subspace;
    ASSERT_TRUE(sub.performed) << sub.note;
    EXPECT_EQ(sub.b_min_source, "inertia_count") << sub.note;
    EXPECT_TRUE(sub.rigorous) << sub.note;
    const auto wb = hs::test::dense_eigenvalues(b, static_cast<const hs::CsrMatrix<double>*>(nullptr));
    EXPECT_GT(sub.b_min, 0.0);
    EXPECT_LE(sub.b_min, wb.front());
    EXPECT_LT(sub.max_sin_bound, 1e-6);
  }

  // Indefinite B: no certificate, no bound.
  const index_t n = 40;
  const auto a = hs::test::laplacian_1d<double>(n);
  auto b = hs::identity<double>(n);
  for (index_t i = 0; i < n; i += 3) b.values[static_cast<std::size_t>(i)] = -1.0;
  auto gcfg = base_config<double>();
  gcfg.target.sigma = 0.3;
  gcfg.target.k = 2;
  s = hs::solve(a, &b, gcfg);
  EXPECT_EQ(s.report.problem, hs::ProblemType::GeneralizedIndefinite);
  EXPECT_FALSE(s.report.subspace.performed);
  EXPECT_NE(s.report.subspace.note.find("indefinite B"), std::string::npos);
}

// subspace_bound = on when the inertia counts do not prove lambda_min(B): the 1-D Laplacian of order
// 2000 has a Jacobi-scaled lambda_min of 1.2e-6, far below the counts' shifts theta/2 and theta/20
// (theta: a 20-step Lanczos estimate from inside, orders of magnitude larger), so both counts find
// negative pivots. The estimate
// that remains (rigorous false) must not exceed the shifts the counts showed to be above
// lambda_min - the default estimate theta/2 is one of them - and the note says what was counted.
TEST(SubspaceBoundSolveReport, OnModeNeverEstimatesAboveAFailedCount) {
  const index_t n = 2000;
  const auto a = hs::identity<double>(n);
  const auto b = hs::test::laplacian_1d<double>(n);
  auto cfg = base_config<double>();
  cfg.target.sigma = 1.0;
  cfg.target.k = 3;
  const auto est = hs::solve(a, &b, cfg);
  ASSERT_TRUE(est.report.success) << est.report.to_json();
  ASSERT_TRUE(est.report.subspace.performed) << est.report.subspace.note;
  EXPECT_EQ(est.report.subspace.b_min_source, "estimate");
  cfg.subspace_bound = hs::Toggle::On;
  const auto on = hs::solve(a, &b, cfg);
  ASSERT_TRUE(on.report.success) << on.report.to_json();
  const auto& sub = on.report.subspace;
  ASSERT_TRUE(sub.performed) << sub.note;
  EXPECT_EQ(sub.b_min_source, "estimate") << sub.note;
  EXPECT_FALSE(sub.rigorous);
  const std::string counted = "the inertia counts of B - mu diag(B) found ";
  ASSERT_NE(sub.note.find(counted), std::string::npos) << sub.note;
  EXPECT_NE(sub.note.find("negative and 0 zero pivot(s) at mu = "), std::string::npos) << sub.note;
  const std::string upper = "lambda_min(D^{-1/2} B D^{-1/2}) <= ";
  const auto at = sub.note.find(upper);
  ASSERT_NE(at, std::string::npos) << sub.note;
  const double below = std::stod(sub.note.substr(at + upper.size()));
  const double dmin = 2.0;  // min_i b_ii; S = B / 2
  EXPECT_LE(sub.b_min, 0.5 * below * dmin * (1.0 + 1e-5)) << sub.note;  // the note prints 6 digits
  EXPECT_LE(sub.b_min, 0.5 * est.report.subspace.b_min) << sub.note;
  EXPECT_GT(sub.b_min, 0.0);
  EXPECT_LT(2.0 * std::pow(std::sin(M_PI / (2.0 * (n + 1))), 2.0), below);  // the count was right
}

}  // namespace
