"""Stub for AURORAZ's keystore when running outside the desktop app.

The SDK does not encrypt or decrypt secrets - AURORAZ desktop does that on
load. If a public-facing module incidentally references the keystore
(it shouldn't), this stub raises so the failure is loud.
"""


class _StubError(NotImplementedError):
    pass


def get_master_key():
    raise _StubError(
        "auroraz-sdk does not include encryption. "
        "AURORAZ desktop handles encryption when loading the plugin."
    )


def reset_master_key_for_test():
    raise _StubError(
        "auroraz-sdk does not include encryption. "
        "AURORAZ desktop handles encryption when loading the plugin."
    )
