# Spin + hardened router exact-source integration

Status: **draft candidate; no executable guest proof at this combined head**.

## Source contract (2026-11-10)
- This branch stacks on Spin #40, which itself stacks on Spin #39.
- The submodule `dependencies/http-routing` is a true Gitlink (mode 160000)
  pinned to router integration PR #51 commit
  `41082647b74a48ce0526762e481562d4a5346f72`.
- Router #51 includes decision admission #43, local bounded route replay,
  nonempty parameter matching and Java compiler pin #49.
- Spin `SOURCE_REF=e6098659c2e1641564bb5835b4dbb92a6a00b1a8`.
  Its `LLVM_SOURCE_REF` and `BACKENDS.json` remain unchanged.

## Execute at exact heads
1. Verify the original Spin PR head, Git tree SHA, router Gitlink commit,
   router Git tree SHA, and Java compiler exact commit/tree SHA. All must
   refer to the same audited sources used in the command.
2. Clean checkout router submodule and Java compiler at those exact commits;
   no cross-org GITHUB_TOKEN checkout of a private source repository.
3. Run `scripts/test.sh` using this Spin checkout and the clean compiler
   checkout. The script itself requires the compiler pin, cleans router
   submodule and executes router guest checks, builder and live HTTP tests.
4. Validate true HTTP socket results: 403 when middleware already replied,
   actor-owned 500 on abandonment, 401 auth, 404/405/OPTIONS, HEAD body
   suppression, keep-alive recovery and bounded admission/timeout handling.
5. Require nonzero job steps, assigned runner, attempt, exact SHA/tree
   receipts, raw logs, negative tests and independent review.

## Explicit limitations
The PR head has **NOT_EXECUTED** end-to-end HTTP evidence. A host-only
canary can establish that alternate-org Actions admits runners but cannot
prove the compiler or Spin semantics. The router Decision remains
non-cryptographic data; cross-generation identity is not fully fenced.
The existing Java adapter is not evidence of LLVM, .NET or NativeAOT
HTTP-serving parity. Do not merge merely because a workflow appears green
without examining executed steps and source-tree identity.
