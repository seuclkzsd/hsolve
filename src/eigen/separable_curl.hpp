// Candidate subspaces for a verified Cartesian curl-curl stencil. This is not a certificate:
// the caller must check the original residuals, rank and completeness on the actual pencil.
#pragma once

#include <string>
#include <vector>

#include "hsolve/dense.hpp"
#include "hsolve/sparse.hpp"

namespace hs::eigen_detail {

/// Requires validated, full-storage real symmetric CSR inputs, B positive definite or nullptr.
/// Infers the natural three-edge-block ordering and checks every entry against a separable
/// stencil. Returns false for unsupported matrices, a target touching the null space or an
/// unresolved boundary multiplet, or insufficient workspace. No case metadata is consulted.
///
/// memory_bytes is the caller's allowance for candidate construction, excluding its later
/// AX/BX, Rayleigh-Ritz and selected-vector storage. On success x has k columns, lambda their
/// model values, and hints the model levels for endpoint proposals only. None of these replace
/// a completeness check on the original matrix. Allocation failures propagate to the caller.
bool separable_curl_candidates(const CsrMatrix<double>& a, const CsrMatrix<double>* b, double sigma,
                               index_t k, double memory_bytes, DenseMatrix<double>& x,
                               std::vector<double>& lambda, std::vector<double>& hints,
                               std::string& why);

/// Complex counterpart for Bloch-periodic Cartesian grids (at least three cells per axis).
/// Infers unit-modulus boundary phases from A and verifies the entire stencil. The same
/// original-pencil verification, workspace and completeness requirements apply.
bool separable_curl_candidates(const CsrMatrix<cplx>& a, const CsrMatrix<cplx>* b, double sigma,
                               index_t k, double memory_bytes, DenseMatrix<cplx>& x,
                               std::vector<double>& lambda, std::vector<double>& hints,
                               std::string& why);

}  // namespace hs::eigen_detail
