// Data protection helpers (docs/FORMATS.md §5): the SHA-256 digests the command line's secure mode
// records instead of input paths (include/hsolve/util.hpp), and the matrix readers' refusal of
// numpy object arrays (whose payload would be a pickle).
#include <gtest/gtest.h>
#include <unistd.h>

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#include "hsolve/error.hpp"
#include "hsolve/io.hpp"
#include "hsolve/util.hpp"

namespace {

std::string digest(const std::string& text) {
  hs::Sha256 sha;
  sha.update(text.data(), text.size());
  return sha.hex();
}

// FIPS 180-2 Appendix B test vectors.
TEST(Sha256, StandardVectors) {
  EXPECT_EQ(digest(""), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
  EXPECT_EQ(digest("abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  EXPECT_EQ(digest("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"),
            "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1");
  EXPECT_EQ(digest(std::string(1000000, 'a')), "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0");
}

TEST(Sha256, ChunkedUpdatesAndFilesAgree) {
  std::string text;
  for (int i = 0; i < 5000; ++i) text += static_cast<char>((i * 131 + 7) % 256);
  hs::Sha256 sha;
  for (std::size_t pos = 0, step = 1; pos < text.size(); pos += step, step = step % 97 + 13)
    sha.update(text.data() + pos, std::min(step, text.size() - pos));
  const std::string chunked = sha.hex();
  EXPECT_EQ(chunked, digest(text));
  const auto path = std::filesystem::temp_directory_path() / ("hsolve_sha256_" + std::to_string(::getpid()));
  {
    std::ofstream out(path, std::ios::binary);
    out.write(text.data(), static_cast<std::streamsize>(text.size()));
  }
  EXPECT_EQ(hs::file_sha256(path.string()), chunked);
  std::filesystem::remove(path);
  try {
    (void)hs::file_sha256(path.string());
    ADD_FAILURE() << "a missing file must throw";
  } catch (const hs::Error& e) {
    EXPECT_EQ(e.code(), hs::Error::Code::Io);
  }
}

// A .npy whose dtype is 'object' carries a pickle: the reader refuses it before reading the payload
// (it has no unpickler at all).
TEST(SecureInput, ObjectArraysAreRefused) {
  const auto path = std::filesystem::temp_directory_path() / ("hsolve_object_" + std::to_string(::getpid()) + ".npy");
  std::string header = "{'descr': '|O', 'fortran_order': False, 'shape': (2, 2), }";
  header.append(64 - (10 + header.size() + 1) % 64, ' ');
  header += '\n';
  std::string bytes = std::string("\x93NUMPY\x01\x00", 8);
  bytes += static_cast<char>(header.size() & 0xff);
  bytes += static_cast<char>(header.size() >> 8);
  bytes += header;
  bytes += "\x80\x02" "cos\nsystem\n(S'touch /tmp/hsolve_pwned'\ntR.";  // a pickle that would run a command
  {
    std::ofstream out(path, std::ios::binary);
    out.write(bytes.data(), static_cast<std::streamsize>(bytes.size()));
  }
  try {
    (void)hs::load_matrix(path.string());
    ADD_FAILURE() << "an object array must be refused";
  } catch (const hs::Error& e) {
    EXPECT_EQ(e.code(), hs::Error::Code::Unsupported) << e.what();
  }
  std::filesystem::remove(path);
}

}  // namespace
