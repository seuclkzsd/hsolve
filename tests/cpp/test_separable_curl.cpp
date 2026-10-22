#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <nlohmann/json.hpp>
#include <numeric>
#include <random>
#include <string>
#include <utility>
#include <vector>

#include "driver/projection.hpp"
#include "eigen/separable_curl.hpp"
#include "hsolve/solver.hpp"
#include "hsolve/sparse.hpp"
#include "support/fixtures.hpp"

namespace {
using hs::index_t;

template <class T>
struct TestPencil {
  hs::CsrMatrix<T> a, b;
};
using Pencil = TestPencil<double>;
using ComplexPencil = TestPencil<hs::cplx>;

// Independent face assembly C^T C: each face has its oriented circulation on up to four
// edges. It does not use the recognizer's row stencils or the modal eigenvalue formula.
Pencil assemble(std::array<index_t, 3> cells, std::array<double, 3> alpha,
                std::array<double, 3> mass) {
  std::array<std::array<index_t, 3>, 3> shape;
  std::array<index_t, 3> length, offset;
  index_t n = 0;
  for (int d = 0; d < 3; ++d) {
    length[d] = 1;
    for (int e = 0; e < 3; ++e) {
      shape[d][e] = cells[e] - (e == d ? 0 : 1);
      length[d] *= shape[d][e];
    }
    offset[d] = n;
    n += length[d];
  }
  auto edge = [&](int d, const std::array<index_t, 3>& p) {
    return offset[d] + (p[0] * shape[d][1] + p[1]) * shape[d][2] + p[2];
  };
  std::vector<index_t> rows, cols;
  std::vector<double> vals;
  for (int normal = 0; normal < 3; ++normal) {
    auto face_shape = cells;
    --face_shape[normal];
    const int e = (normal + 1) % 3, f = (normal + 2) % 3;
    for (index_t i = 0; i < face_shape[0]; ++i)
      for (index_t j = 0; j < face_shape[1]; ++j)
        for (index_t k = 0; k < face_shape[2]; ++k) {
          const std::array<index_t, 3> face{i, j, k};
          std::vector<std::pair<index_t, double>> circulation;
          for (int u : {0, 1}) {
            auto p = face;
            p[e] -= u;
            if (p[e] >= 0 && p[e] < cells[e] - 1)
              circulation.emplace_back(edge(f, p),
                                       (u == 0 ? 1 : -1) * std::sqrt(alpha[e] * mass[f]));
            p = face;
            p[f] -= u;
            if (p[f] >= 0 && p[f] < cells[f] - 1)
              circulation.emplace_back(edge(e, p),
                                       (u == 0 ? -1 : 1) * std::sqrt(alpha[f] * mass[e]));
          }
          for (const auto& a : circulation)
            for (const auto& b : circulation) {
              rows.push_back(a.first);
              cols.push_back(b.first);
              vals.push_back(a.second * b.second);
            }
        }
  }
  Pencil p{hs::csr_from_coo(n, n, rows, cols, vals, true), hs::identity<double>(n)};
  for (int d = 0; d < 3; ++d)
    for (index_t i = offset[d]; i < offset[d] + length[d]; ++i) p.b.values[i] = mass[d];
  return p;
}

template <class T>
hs::SolverConfig target(const TestPencil<T>& p, index_t minimum = 3) {
  auto w = hs::test::dense_eigenvalues(p.a, &p.b);
  std::vector<double> positive;
  for (double x : w)
    if (x > 1e-9 * w.back()) positive.push_back(x);
  hs::SolverConfig c;
  c.threads = 2;
  c.memory_budget_gb = 2;
  c.structure_candidates = hs::Toggle::Auto;  // the optional path these tests exercise (off by default)
  const std::size_t first = hs::is_complex_v<T> ? std::min<std::size_t>(8, positive.size() - 2) : 0;
  c.target.sigma = 0.5 * (positive[first] + positive[first + 1]);
  std::sort(w.begin(), w.end(), [&](double a, double b) {
    return std::abs(a - c.target.sigma) < std::abs(b - c.target.sigma);
  });
  c.target.k = minimum;
  while (c.target.k < static_cast<index_t>(w.size()) &&
         std::abs(std::abs(w[c.target.k] - c.target.sigma) -
                  std::abs(w[c.target.k - 1] - c.target.sigma)) < 1e-8)
    ++c.target.k;
  return c;
}

template <class T>
void expect_reference(const TestPencil<T>& p, const hs::SolverConfig& c,
                      const hs::Solution<T>& solution) {
  ASSERT_TRUE(solution.report.success) << solution.report.to_json();
  ASSERT_EQ(solution.eigenvalues.size(), static_cast<std::size_t>(c.target.k));
  for (const auto& pair : solution.report.pairs) EXPECT_LE(pair.backward_error, c.tol);
  auto reference = hs::test::dense_eigenvalues(p.a, &p.b);
  std::sort(reference.begin(), reference.end(), [&](double a, double b) {
    return std::abs(a - c.target.sigma) < std::abs(b - c.target.sigma);
  });
  reference.resize(c.target.k);
  auto got = solution.eigenvalues;
  std::sort(reference.begin(), reference.end());
  std::sort(got.begin(), got.end());
  for (std::size_t i = 0; i < got.size(); ++i) EXPECT_NEAR(got[i], reference[i], 1e-9);
  EXPECT_TRUE(solution.report.certificate.passed);
  EXPECT_EQ(solution.report.certificate.method, "exact");
}

TEST(SeparableCurl, IndependentFaceAssemblyAndDenseReference) {
  std::mt19937_64 random(260016);
  for (int trial = 0; trial < 8; ++trial) {
    const std::array<index_t, 3> cells{3 + index_t(random() % 3), 3 + index_t(random() % 3),
                                       3 + index_t(random() % 3)};
    const std::array<double, 3> alpha{5.1 + (random() % 100) * .07, 7.3 + (random() % 100) * .09,
                                      8.7 + (random() % 100) * .11};
    const auto p =
        assemble(cells, alpha,
                 trial % 2 ? std::array<double, 3>{1, 1, 1} : std::array<double, 3>{.2, .37, .59});
    const auto cfg = target(p);
    const auto solution = hs::solve(p.a, &p.b, cfg);
    expect_reference(p, cfg, solution);
    EXPECT_EQ(solution.report.candidate_source, "separable_cartesian_curl");
    EXPECT_EQ(solution.report.op_applies, 0);
    EXPECT_EQ(solution.report.block_size, 0);
    EXPECT_EQ(nlohmann::json::parse(solution.report.to_json())["candidate_source"],
              "separable_cartesian_curl");
    if (trial % 2) {
      const auto standard = hs::solve(p.a, nullptr, cfg);
      expect_reference(p, cfg, standard);
      EXPECT_EQ(standard.report.candidate_source, "separable_cartesian_curl");
    }
  }
}

TEST(SeparableCurl, VerifiesInteriorCoefficientsAndMass) {
  const auto base = assemble({4, 5, 6}, {9.2, 13.7, 21.3}, {.3, .5, .7});
  for (int variant = 0; variant < 3; ++variant) {
    auto p = base;
    if (variant == 0) {
      const index_t row = p.a.nrows / 2;
      for (index_t q = p.a.rowptr[row]; q < p.a.rowptr[row + 1]; ++q)
        if (p.a.colind[q] == row) p.a.values[q] *= 1.001;
    } else if (variant == 1) {
      p.b.values[p.b.nrows / 2] *= 1.001;
    } else {
      // A reverse symmetric permutation preserves the spectrum and Hermitian property.
      std::vector<index_t> rows, cols;
      std::vector<double> values;
      for (index_t row = 0; row < p.a.nrows; ++row)
        for (index_t q = p.a.rowptr[row]; q < p.a.rowptr[row + 1]; ++q) {
          rows.push_back(p.a.nrows - 1 - row);
          cols.push_back(p.a.nrows - 1 - p.a.colind[q]);
          values.push_back(p.a.values[q]);
        }
      p.a = hs::csr_from_coo(p.a.nrows, p.a.ncols, rows, cols, values, true);
      std::reverse(p.b.values.begin(), p.b.values.end());
    }
    const auto cfg = target(p);
    const auto solution = hs::solve(p.a, &p.b, cfg);
    expect_reference(p, cfg, solution);
    EXPECT_EQ(solution.report.candidate_source, "iterative");
    EXPECT_GT(solution.report.op_applies, 0);
  }
}

TEST(SeparableCurl, RejectsPartialMultipletsNullSpaceAndInsufficientWorkspace) {
  const auto p = assemble({4, 4, 4}, {16, 16, 16}, {1, 1, 1});
  const auto cfg = target(p);
  hs::DenseMatrix<double> x;
  std::vector<double> lambda, hints;
  std::string why;
  EXPECT_FALSE(hs::eigen_detail::separable_curl_candidates(p.a, &p.b, cfg.target.sigma,
                                                           cfg.target.k, 0, x, lambda, hints, why));
  EXPECT_TRUE(x.empty());
  EXPECT_NE(why.find("budget"), std::string::npos);
  EXPECT_FALSE(
      hs::eigen_detail::separable_curl_candidates(p.a, &p.b, 0, 3, 1e8, x, lambda, hints, why));
  EXPECT_FALSE(hs::eigen_detail::separable_curl_candidates(p.a, &p.b, cfg.target.sigma, 1, 1e8, x,
                                                           lambda, hints, why));
}

TEST(SeparableCurl, ExactCertificateRecoversAnInjectedMissingPair) {
  const auto p = assemble({5, 6, 7}, {16.2, 29.7, 33.1}, {.2, .5, .9});
  auto cfg = target(p, 4);
  cfg.certificate_fault_drop = 1;
  const auto solution = hs::solve(p.a, &p.b, cfg);
  expect_reference(p, cfg, solution);
  EXPECT_EQ(solution.report.candidate_source, "separable_cartesian_curl");
  EXPECT_GT(solution.report.op_applies, 0);
}

TEST(SeparableCurl, RecoveryInitializesFactorsAtAnEigenvalueTarget) {
  const auto p = assemble({4, 4, 4}, {16, 16, 16}, {1, 1, 1});
  auto cfg = target(p);
  cfg.certificate_fault_drop = 1;
  const auto solution = hs::solve(p.a, &p.b, cfg);
  expect_reference(p, cfg, solution);
  EXPECT_EQ(solution.report.candidate_source, "separable_cartesian_curl");
  EXPECT_GT(solution.report.op_applies, 0);
}

TEST(SeparableCurl, HonorsExplicitMethodAndCertificateFailure) {
  const auto p = assemble({4, 5, 6}, {9.2, 13.7, 21.3}, {.3, .5, .7});
  auto cfg = target(p);
  cfg.method = hs::Method::ShiftInvertLanczos;
  auto solution = hs::solve(p.a, &p.b, cfg);
  expect_reference(p, cfg, solution);
  EXPECT_EQ(solution.report.candidate_source, "iterative");
  cfg.method = hs::Method::Auto;
  cfg.certificate_fault_count = 1 | 2 | 16;
  solution = hs::solve(p.a, &p.b, cfg);
  EXPECT_EQ(solution.report.candidate_source, "separable_cartesian_curl");
  EXPECT_FALSE(solution.report.success);
  EXPECT_TRUE(solution.report.certificate.performed);
  EXPECT_FALSE(solution.report.certificate.passed);
}

// Independently assemble C^H C from face circulations with forward periodic differences.
// The recognizer, its expected row template and its modal formula are not used here.
ComplexPencil assemble_bloch(std::array<index_t, 3> cells, std::array<double, 3> alpha,
                            std::array<double, 3> mass, std::array<double, 3> phase) {
  using hs::cplx;
  const index_t volume = cells[0] * cells[1] * cells[2], n = 3 * volume;
  auto edge = [&](int d, const std::array<index_t, 3>& p) {
    return d * volume + (p[0] * cells[1] + p[1]) * cells[2] + p[2];
  };
  std::vector<index_t> rows, cols;
  std::vector<cplx> values;
  for (int normal = 0; normal < 3; ++normal) {
    const int e = (normal + 1) % 3, f = (normal + 2) % 3;
    for (index_t i = 0; i < cells[0]; ++i)
      for (index_t j = 0; j < cells[1]; ++j)
        for (index_t k = 0; k < cells[2]; ++k) {
          const std::array<index_t, 3> pos{i, j, k};
          std::vector<std::pair<index_t, cplx>> circulation;
          for (int derivative : {e, f}) {
            const int component = derivative == e ? f : e;
            const double sign = derivative == e ? 1 : -1;
            const double scale = sign * std::sqrt(alpha[derivative] * mass[component]);
            circulation.emplace_back(edge(component, pos), -scale);
            auto next = pos;
            ++next[derivative];
            cplx wrap = 1;
            if (next[derivative] == cells[derivative]) {
              next[derivative] = 0;
              wrap = std::polar(1.0, phase[derivative]);
            }
            circulation.emplace_back(edge(component, next), scale * wrap);
          }
          for (const auto& left : circulation)
            for (const auto& right : circulation) {
              rows.push_back(left.first);
              cols.push_back(right.first);
              values.push_back(std::conj(left.second) * right.second);
            }
        }
  }
  ComplexPencil p{hs::csr_from_coo(n, n, rows, cols, values, true), hs::identity<cplx>(n)};
  for (int d = 0; d < 3; ++d)
    for (index_t row = d * volume; row < (d + 1) * volume; ++row) p.b.values[row] = mass[d];
  return p;
}

TEST(SeparableBloch, IndependentFacesDenseReferenceAndSpecialPhases) {
  std::mt19937_64 random(290016);
  for (int trial = 0; trial < 9; ++trial) {
    const std::array<index_t, 3> cells{3 + index_t(random() % 3), 3 + index_t(random() % 3),
                                      3 + index_t(random() % 3)};
    const std::array<double, 3> alpha{5.1 + (random() % 100) * .07, 7.3 + (random() % 100) * .09,
                                     8.7 + (random() % 100) * .11};
    std::array<double, 3> phase{.3 + .01 * (random() % 100), -.7 - .01 * (random() % 100), .23};
    if (trial == 0) phase = {0, 0, 0};
    if (trial == 1) phase = {std::acos(-1.0), 0, 0};
    if (trial == 2) phase = {1e-12, -1e-12, 0};
    const auto p = assemble_bloch(cells, alpha,
        trial % 2 ? std::array<double, 3>{1, 1, 1} : std::array<double, 3>{.2, .37, .59}, phase);
    const auto cfg = target(p, 4);
    const auto solution = hs::solve(p.a, &p.b, cfg);
    expect_reference(p, cfg, solution);
    EXPECT_EQ(solution.report.candidate_source, "separable_bloch_curl") << trial;
    EXPECT_EQ(solution.report.op_applies, 0);
    EXPECT_EQ(solution.report.block_size, 0);
    if (trial % 2) {
      const auto standard = hs::solve(p.a, nullptr, cfg);
      expect_reference(p, cfg, standard);
      EXPECT_EQ(standard.report.candidate_source, "separable_bloch_curl");
    }
  }
}

TEST(SeparableBloch, RejectsInteriorAndBoundaryChangesAndNonuniformMass) {
  const auto base = assemble_bloch({3, 4, 5}, {11.2, 17.1, 20.3}, {.3, .5, .7}, {.7, -1.1, .3});
  for (int variant = 0; variant < 4; ++variant) {
    auto p = base;
    if (variant == 0) {
      const index_t row = p.a.nrows / 2;
      for (index_t q = p.a.rowptr[row]; q < p.a.rowptr[row + 1]; ++q)
        if (p.a.colind[q] == row) p.a.values[q] *= 1.001;
    } else if (variant == 1) {
      p.b.values[p.b.nrows / 2] *= 1.001;
    } else {
      // Change a Hermitian boundary pair away from the rows used to infer the phases.
      const index_t row = 20, col = 24;
      for (index_t q = p.a.rowptr[row]; q < p.a.rowptr[row + 1]; ++q)
        if (p.a.colind[q] == col)
          p.a.values[q] *= variant == 2 ? hs::cplx{1.001} : std::polar(1.0, .01);
      for (index_t q = p.a.rowptr[col]; q < p.a.rowptr[col + 1]; ++q)
        if (p.a.colind[q] == row)
          p.a.values[q] *= variant == 2 ? hs::cplx{1.001} : std::polar(1.0, -.01);
    }
    const auto cfg = target(p, 4);
    const auto solution = hs::solve(p.a, &p.b, cfg);
    expect_reference(p, cfg, solution);
    EXPECT_EQ(solution.report.candidate_source, "iterative") << variant;
    EXPECT_GT(solution.report.op_applies, 0);
  }
}

TEST(SeparableBloch, WorkspaceNullSpacePartialMultipletsAndUnsupportedGrid) {
  auto p = assemble_bloch({3, 4, 5}, {11.2, 17.1, 20.3}, {.3, .5, .7}, {.7, -1.1, .3});
  const auto cfg = target(p, 4);
  hs::DenseMatrix<hs::cplx> x;
  std::vector<double> lambda, hints;
  std::string why;
  EXPECT_FALSE(hs::eigen_detail::separable_curl_candidates(p.a, &p.b, cfg.target.sigma,
                                                           cfg.target.k, 0, x, lambda, hints, why));
  EXPECT_TRUE(x.empty());
  EXPECT_NE(why.find("budget"), std::string::npos);
  EXPECT_FALSE(hs::eigen_detail::separable_curl_candidates(p.a, &p.b, 0, 4, 1e8, x, lambda, hints, why));
  EXPECT_FALSE(hs::eigen_detail::separable_curl_candidates(p.a, &p.b, cfg.target.sigma,
                                                           1, 1e8, x, lambda, hints, why));
  const auto degenerate = assemble_bloch({3, 3, 3}, {16, 16, 16}, {1, 1, 1}, {0, 0, 0});
  EXPECT_FALSE(hs::eigen_detail::separable_curl_candidates(degenerate.a, &degenerate.b, 48,
                                                           2, 1e8, x, lambda, hints, why));
  p = assemble_bloch({2, 4, 5}, {11.2, 17.1, 20.3}, {.3, .5, .7}, {.7, -1.1, .3});
  EXPECT_FALSE(hs::eigen_detail::separable_curl_candidates(p.a, &p.b, cfg.target.sigma,
                                                           4, 1e8, x, lambda, hints, why));
}

TEST(SeparableBloch, OriginalCertificateAndRerunRemainRequired) {
  const auto p = assemble_bloch({3, 4, 5}, {11.2, 17.1, 20.3}, {.3, .5, .7}, {.7, -1.1, .3});
  auto cfg = target(p, 4);
  cfg.certificate_fault_drop = 1;
  auto solution = hs::solve(p.a, &p.b, cfg);
  expect_reference(p, cfg, solution);
  EXPECT_EQ(solution.report.candidate_source, "separable_bloch_curl");
  EXPECT_GT(solution.report.op_applies, 0);
  cfg.certificate_fault_drop = 0;
  cfg.certificate_fault_count = 1 | 2 | 16;
  solution = hs::solve(p.a, &p.b, cfg);
  EXPECT_FALSE(solution.report.success);
  EXPECT_EQ(solution.report.candidate_source, "separable_bloch_curl");
  EXPECT_TRUE(solution.report.certificate.performed);
  EXPECT_FALSE(solution.report.certificate.passed);
  cfg.certificate_fault_count = 0;
  cfg.method = hs::Method::ShiftInvertLanczos;
  solution = hs::solve(p.a, &p.b, cfg);
  expect_reference(p, cfg, solution);
  EXPECT_EQ(solution.report.candidate_source, "iterative");
}

// The structure-recognition path is off by default: a matrix it would accept takes exactly the
// general path, as with the key off or an explicit method.
TEST(SeparableCurl, OffByDefaultTakesTheGeneralPath) {
  EXPECT_EQ(hs::SolverConfig{}.structure_candidates, hs::Toggle::Off);
  const auto real = assemble({4, 5, 6}, {9.2, 13.7, 21.3}, {.3, .5, .7});
  const auto bloch = assemble_bloch({3, 4, 5}, {11.2, 17.1, 20.3}, {.3, .5, .7}, {.7, -1.1, .3});
  const auto check = [](const auto& p) {
    auto cfg = target(p, 4);
    cfg.deterministic = true;
    cfg.structure_candidates = hs::Toggle::Auto;
    const auto structured = hs::solve(p.a, &p.b, cfg);
    EXPECT_NE(structured.report.candidate_source, "iterative");
    cfg.structure_candidates = hs::Toggle::Off;
    const auto off = hs::solve(p.a, &p.b, cfg);
    expect_reference(p, cfg, off);
    EXPECT_EQ(off.report.candidate_source, "iterative");
    EXPECT_GT(off.report.op_applies, 0);
    EXPECT_GT(off.report.block_size, 0);
    auto def = hs::parse_config("{}");
    def.target = cfg.target;
    def.threads = cfg.threads;
    def.memory_budget_gb = cfg.memory_budget_gb;
    def.deterministic = true;
    const auto by_default = hs::solve(p.a, &p.b, def);
    EXPECT_EQ(by_default.report.candidate_source, "iterative");
    // Bitwise the same run as the explicit general method (deterministic factorizations).
    cfg.method = hs::Method::ShiftInvertLanczos;
    const auto general = hs::solve(p.a, &p.b, cfg);
    ASSERT_EQ(by_default.eigenvalues.size(), general.eigenvalues.size());
    for (std::size_t i = 0; i < general.eigenvalues.size(); ++i)
      EXPECT_EQ(by_default.eigenvalues[i], general.eigenvalues[i]) << i;
    EXPECT_EQ(by_default.report.op_applies, general.report.op_applies);
  };
  check(real);
  check(bloch);
}
}  // namespace
