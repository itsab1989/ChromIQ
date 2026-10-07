# AFTER EVERY BUMP: python scripts/make_preset_certificates.py, and commit
# data/preset_certificates.json in the same commit. The built-in presets'
# metric certificates are keyed by this version (Knut #182 6045500910 Q5), so
# without it every built-in is worked out again on the user's machine, and
# tests/test_beta12_b_preset_certificates.py fails until it is done.
APP_VERSION = "4.3.3-beta.11"
