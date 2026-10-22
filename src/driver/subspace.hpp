// A-posteriori bounds on the eigenvector subspace angles of a HEP/GHEP result (driver-internal;
// docs/DESIGN.md §3.6-8c, SolveReport::subspace).
//
// In the B inner product the pencil (A, B), B Hermitian positive definite, is the Hermitian
// matrix C = B^{-1/2} A B^{-1/2}: a returned block X (B-orthonormal up to rounding) is Y = B^{1/2} X
// and its residual block C Y - Y Theta = B^{-1/2} (A X - B X Theta). With G = X^H B X and
// eps >= ||G - I||_2 < 1:
//   * Kahan (Parlett, The Symmetric Eigenvalue Problem, Thm 11.5.1), applied to the orthonormal
//     Y G^{-1/2} with H = Theta: C has |c| eigenvalues (distinct indices) within
//       eta = ||B^{-1/2} R||_F / sqrt(1 - eps) + sqrt(1 + eps) spread(Theta) (1/sqrt(1 - eps) - 1)
//     of the theta's of a group c (the commutator of Theta and G^{-1/2} gives the second term);
//   * Davis-Kahan sin(Theta) (Frobenius norm): if every eigenvalue of C outside the exact spectral
//     subspace E is at least delta away from every theta of the group, then with
//     S = E_perp^H Y, Lambda_2 S - S Theta = E_perp^H R, so ||S||_F <= ||R||_F / delta and
//       ||sin Theta(span X, E)||_F <= ||B^{-1/2} R||_F / (delta sqrt(1 - eps)).
// A certified window [lower, upper) holds exactly `count` eigenvalues (the certificate's Sylvester
// counts) and no eigenvalue outside it is nearer to a theta inside than the window ends. When a
// window holds as many computed pairs (returned, plus those found inside but not returned: beyond
// k) as eigenvalues, the pairs are grouped into clusters whose Kahan intervals J_c are disjoint and
// inside the window: each J_c then holds exactly |c| eigenvalues, the window none outside the J's,
// and delta_c is the distance to the window ends and to the other J's. A window with fewer computed
// pairs than eigenvalues (or whose J's cannot be kept inside it) is one group compared with the
// window's whole spectral subspace (delta: distance to the window ends).
// Rounding: residuals, Gram entries and B^{-1}-norms are computed in floating point; each carries
// an a-priori bound of its rounding error (Higham, Accuracy and Stability, §3.1; factor 2 of slack
// for complex arithmetic), so the bounds hold for the exact quantities. The products with A and B
// are bounded componentwise (gamma |A| |x|, gamma |B| |x|: one more product with |A|, |B| and |x|),
// and a B^{-1}-norm by the smaller of ||v|| / sqrt(lambda_min(B)) and the Jacobi-weighted
// ||D^{-1/2} v|| / sqrt(lambda_min(D^{-1/2} B D^{-1/2})), so a badly scaled B does not inflate them.
// The scalar steps are one-sided too: eta and the bound carry a gamma factor for their roundings
// (1/sqrt(1 - eps) - 1 is formed without cancellation), the ends of the Kahan intervals are rounded
// outward and the gaps downward (std::nextafter of the value rounded to nearest), so the
// disjointness and inside-the-window comparisons are exact statements about the exact intervals.
#pragma once

#include <limits>
#include <string>
#include <vector>

#include "hsolve/dense.hpp"
#include "hsolve/solver.hpp"
#include "hsolve/sparse.hpp"
#include "hsolve/types.hpp"

namespace hs::driver {

/// Neighbouring eigenvalues closer than kSubspaceClusterRtol * (max |lambda| + scale) form one
/// cluster (the rule and default tolerance of the evaluator's reference clusters, tools/eval).
constexpr double kSubspaceClusterRtol = 1e-6;

/// A window of the passed certificate: exactly `count` eigenvalues of the pencil lie in
/// [lower, upper) (lower may be -inf, upper +inf).
struct CertifiedWindow {
  double lower = 0.0;
  double upper = 0.0;
  index_t count = 0;
};

/// A lower bound (or, when !proven, an estimate) of lambda_min(B).
struct BMinBound {
  double value = 1.0;
  bool proven = true;
  /// "identity", "diagonal", "gershgorin", "incomplete_cholesky", "inertia_count", "estimate"
  std::string source = "identity";
  /// The same for the Jacobi-scaled S = D^{-1/2} B D^{-1/2}, D = diag(B) (0: none). B^{-1}-norms
  /// are bounded by both, v^H B^{-1} v <= min(||v||^2 / value, ||D^{-1/2} v||^2 / scaled): the
  /// second is far smaller for a badly scaled B (value = scaled * min_i b_ii at best).
  double scaled = 0.0;
  /// Not proven although subspace_bound = on: why (the inertia counts' outcome); else empty.
  std::string note;
};

/// Where the time of a bound goes (for the event log; filled when SubspaceOptions::diagnostics is
/// set).
struct SubspaceDiagnostics {
  double residual_s = 0.0;  ///< residuals and their B^{-1}-norms (CG included)
  double cg_s = 0.0;        ///< of which the CG iterations
  int cg_iterations = 0;    ///< largest iteration count of a CG block
  double gram_s = 0.0;      ///< Gram defects of the groups
};

struct SubspaceOptions {
  double scale = 1.0;                         ///< ||A||_2 / ||B||_2 (cluster tolerance)
  double cluster_rtol = kSubspaceClusterRtol;
  /// Memory the computation may allocate (bytes): column chunks of the residual and CG blocks.
  double memory_bytes = std::numeric_limits<double>::infinity();
  BMinBound b_min;                            ///< for B != I (B = I: ignored)
  bool b_diagonal = false;                    ///< B is diagonal: exact weights, no CG
  int cg_max_iterations = 300;                ///< general B: Jacobi-preconditioned CG per column
  double cg_tol = 1e-10;                      ///< ... until ||B z - r|| <= cg_tol ||r||
  SubspaceDiagnostics* diagnostics = nullptr;  ///< receives the time split (optional)
};

/// The bounds for the returned pairs (returned, columns of x) of the pencil (a, b), b == nullptr
/// meaning B = I, against the certified windows. `unreturned` / `extra` are pairs computed inside
/// the windows that the target does not return (beyond k; may be empty, 0 columns): a window's
/// clusters are formed only when its returned and unreturned pairs together are as many as its
/// eigenvalues. Fills the groups, residual_norm, b_min, b_min_source, max_sin_bound and note of
/// the result (performed = true; rigorous only says whether b_min is proven - the caller combines
/// it with the certificate's), and per_pair[j] for the returned pairs (NaN: no bound for pair j:
/// outside every window, no gap, vectors not numerically independent). Throws OutOfMemoryBudget
/// when not even one column's workspace fits opt.memory_bytes.
template <class T>
SubspaceReport subspace_bounds(const CsrMatrix<T>& a, const CsrMatrix<T>* b, const std::vector<double>& returned,
                               const DenseMatrix<T>& x, const std::vector<double>& unreturned,
                               const DenseMatrix<T>& extra, const std::vector<CertifiedWindow>& windows,
                               const SubspaceOptions& opt, std::vector<double>& per_pair);

/// rho_j >= ||B^{-1/2} (A x_j - lambda_j B x_j)||_2 for every column (exact residual: the rounding
/// of its evaluation, bounded componentwise by gamma (|A| |x_j| + |lambda_j| |B| |x_j|), and of the
/// B^{-1}-norm is included). abs_b_norms (optional) receives upper bounds of || |B| |x_j| ||_2
/// (B = I: ||x_j||_2) for the rounding of the Gram matrices. Exposed for tests.
template <class T>
std::vector<double> residual_b_inverse_norms(const CsrMatrix<T>& a, const CsrMatrix<T>* b,
                                             const std::vector<double>& lambda, const DenseMatrix<T>& x,
                                             const SubspaceOptions& opt,
                                             std::vector<double>* abs_b_norms = nullptr);

/// Rigorous Gershgorin lower bounds of lambda_min(b) (plain) and of lambda_min of the Jacobi-scaled
/// diag(b)^{-1/2} b diag(b)^{-1/2} (scaled), the rounding of the row sums bounded; a value <= 0
/// proves nothing. min_diagonal = min_i b_ii. O(nnz(b)).
struct GershgorinBounds {
  double plain = 0.0;
  double scaled = 0.0;
  double min_diagonal = 0.0;
};
template <class T>
GershgorinBounds gershgorin_bounds(const CsrMatrix<T>& b);

/// The larger of the two Gershgorin bounds as a bound of lambda_min(b) (scaled * min b_ii for the
/// scaled one), 0 when Gershgorin proves nothing.
template <class T>
double gershgorin_lambda_min(const CsrMatrix<T>& b);

}  // namespace hs::driver
