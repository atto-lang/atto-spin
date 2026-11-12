# PR #5 — pinned Spin compiler integration semantic reconciliation

Historical branch `a8b3fd42d33facbb6440135bf77d0929cfab97a9`; current main `87d8123aa22febc3b3ee469a479242941064250c`.

The historical request was to repin to compiler SHA `edea24f9bf980025b68650b749a3ef0fc1813c20`. Current main instead pins `3f679db71f392d461dd5cb6f8a15e36dd1dcf5e6`, and its shell test script already contains the historical runner failure-status fixes (identical blob to this old PR). **Preserve the current SHA** rather than silently rolling back verified dependency provenance to the older `edea24f`.

Current Spin contract: require exactly pinned clean compiler checkout and fail closed on missing/running-but-failed compiler, invalid or floating reference, and non-empty/unreadable git status. Spin also must require exact clean HTTP routing gitlink dependency and no automatic fallback to an unrelated router checkout.

Add `tests/source-ref-forward-port.sh` as a small source-free **shape** gate: validates full lowercase immutable 40-hex ref and verifies the test runner still contains the relevant admission checks. It does not prove the compiler at that SHA was built or successfully ran; an inspected source string alone is not attestation.

This reconciliation intentionally changes neither stable `SOURCE_REF` nor existing test runner logic. Release needs exact-source compiler and dependent package execution with output matching its pinned oracle, plus authorized Actions/self-hosted evidence and independent review. Do not treat Git mergeability as a pin-upgrade success.
