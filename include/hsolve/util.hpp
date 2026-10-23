// Small utilities: timing, memory accounting, threading info, version.
#pragma once

#include <chrono>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>

namespace hs {

class Timer {
 public:
  Timer() : t0_(std::chrono::steady_clock::now()) {}
  void reset() { t0_ = std::chrono::steady_clock::now(); }
  double seconds() const {
    return std::chrono::duration<double>(std::chrono::steady_clock::now() - t0_).count();
  }

 private:
  std::chrono::steady_clock::time_point t0_;
};

/// Peak resident set size of this process (getrusage ru_maxrss), bytes.
std::int64_t peak_rss_bytes();
/// Current resident set size (/proc/self/statm), bytes; -1 if unavailable.
std::int64_t current_rss_bytes();
/// Threads the library will use for OpenMP regions (omp_get_max_threads(), or 1 without OpenMP).
int max_threads();

// ------------------------------------------------------------------------- memory limits

/// Environment variable in which a caller declares the memory a run may use, in GiB (2^30 bytes,
/// like SolverConfig::memory_budget_gb): a positive finite number. tools/run/guard.py exports the
/// RSS cap it enforces on the run, so a guarded run sees its cap without a cgroup.
inline constexpr const char* kMemoryLimitEnv = "HSOLVE_MEMORY_LIMIT_GB";

/// The quantity of this process's memory a limit applies to (detect_memory_limits' sources).
enum class MemoryMeasure {
  Resident,      ///< resident memory, RSS: the cgroup, HSOLVE_MEMORY_LIMIT_GB (the guard), MemTotal
  AddressSpace,  ///< virtual address space, VmSize: RLIMIT_AS (`ulimit -v`). It also counts what is
                 ///< reserved but never touched - MUMPS' workspace up to its ICNTL(23) cap, thread
                 ///< stacks, malloc arenas, BLAS buffers - and so exceeds RSS by GBs
  Data,          ///< private writable mappings, VmData: RLIMIT_DATA (Linux >= 4.7; older kernels
                 ///< limit only the brk heap, which malloc then bypasses)
};
/// This process's memory in `measure`, bytes (/proc/self/statm, /proc/self/status); -1 if
/// unavailable.
std::int64_t memory_in_use_bytes(MemoryMeasure measure);
/// High-water mark of the address space (VmPeak of /proc/self/status), bytes; -1 if unavailable.
std::int64_t peak_address_space_bytes();
/// The measure a limit source applies to (MemoryLimitSource::name; unknown names: Resident).
MemoryMeasure measure_of(const std::string& source);
/// "resident", "address_space" or "data".
const char* to_string(MemoryMeasure measure);

/// One source of a memory limit of this process (detect_memory_limits).
struct MemoryLimitSource {
  std::string name;    ///< "cgroup", "env", "rlimit_as", "rlimit_data" or "mem_total"
  double gib = -1.0;   ///< the limit in GiB (2^30 bytes); < 0: this source sets none
  std::string detail;  ///< where it was read, or why it sets none (unlimited, absent, unreadable)
};

/// Every memory limit of this process that detect_memory_limits could read, and the smallest.
struct MemoryLimits {
  std::vector<MemoryLimitSource> sources;  ///< all probed sources, in the order listed above
  double gib = -1.0;                       ///< smallest limit of a source that sets one; < 0: none
  std::string source;                      ///< name of that source ("" when none)
};

/// Where detect_memory_limits reads from. The defaults probe this process; tests replace them.
struct MemoryProbe {
  std::string root;              ///< prefix of /proc/self/cgroup, /proc/meminfo, /sys/fs/cgroup
  bool use_environment = true;   ///< read kMemoryLimitEnv from the environment ...
  std::string env_value;         ///< ... else this value ("" = not set)
  bool use_rlimits = true;       ///< query getrlimit(RLIMIT_AS / RLIMIT_DATA) ...
  std::uint64_t rlimit_as = std::numeric_limits<std::uint64_t>::max();    ///< ... else these
  std::uint64_t rlimit_data = std::numeric_limits<std::uint64_t>::max();  ///< (max = unlimited)
};

/// The memory limits that apply to this process (docs/DESIGN.md §3.6-3):
///   cgroup      the memory cgroup's limit: v2 memory.max, v1 memory.limit_in_bytes (and the v1
///               hierarchical_memory_limit of memory.stat), the smallest along the path of
///               /proc/self/cgroup up to the hierarchy's root ("max" / 2^63-ish = unlimited); a
///               container that shows its own cgroup as "/" is read at the mount's root;
///   env         kMemoryLimitEnv (GiB), e.g. the guard's cap;
///   rlimit_as   RLIMIT_AS when finite (it limits VIRTUAL memory, MemoryMeasure::AddressSpace:
///               stricter than an RSS limit of equal size, so a budget derived from it is planned
///               against the address space, DESIGN §3.6-3);
///   rlimit_data RLIMIT_DATA when finite;
///   mem_total   MemTotal of /proc/meminfo (the whole machine; MemAvailable is not used, so the
///               decision does not depend on what other processes hold at the moment).
/// Unreadable or malformed sources set no limit (their detail says why). Never throws.
MemoryLimits detect_memory_limits(const MemoryProbe& probe = {});

/// `text` without file system paths, for reports in secure mode (SolverConfig::secure): every
/// whitespace-separated word that contains a '/' is replaced by its last path component
/// ("/sys/fs/cgroup/<slice>/memory.max" -> "memory.max", "no /proc/meminfo" -> "no meminfo"), so
/// that no directory name (user, job or container ids) remains; a word that is only slashes
/// becomes "(path)". The other characters, whitespace included, are kept.
std::string strip_paths(const std::string& text);

/// SHA-256 (FIPS 180-4) of a byte stream, for recording inputs by content instead of by path
/// (SolverConfig::secure, docs/FORMATS.md §5). update() any number of times, then hex() once.
class Sha256 {
 public:
  Sha256();
  void update(const void* data, std::size_t size);
  /// Lower-case hex digest (64 characters); the object must not be updated afterwards.
  std::string hex();

 private:
  void block(const unsigned char* p);
  std::uint32_t h_[8];
  unsigned char buf_[64];
  std::size_t used_ = 0;
  std::uint64_t total_ = 0;
};
/// SHA-256 of a whole file (read in 1 MiB chunks); throws hs::Error(Io) when it cannot be read.
std::string file_sha256(const std::string& path);

/// Library version string, e.g. "1.0.0".
const char* version();
/// Build description: compiler, flags, MUMPS/BLAS versions (for reports).
std::string build_info();

}  // namespace hs
