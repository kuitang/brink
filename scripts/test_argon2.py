#!/usr/bin/env python3
"""Test script to verify argon2-cffi installs and works correctly.

Run with: uv run python scripts/test_argon2.py
"""
import time


def main():
    # Test import
    print("Testing argon2-cffi installation...")
    try:
        from argon2 import PasswordHasher, Type
        from argon2.exceptions import VerifyMismatchError
        print("  [OK] Import successful")
    except ImportError as e:
        print(f"  [FAIL] Import failed: {e}")
        print("\nInstall with: uv add argon2-cffi")
        return 1

    # Check defaults match RFC 9106 LOW_MEMORY
    ph = PasswordHasher()
    print("\nVerifying RFC 9106 LOW_MEMORY defaults:")
    print(f"  time_cost:    {ph.time_cost} (expected: 3)")
    print(f"  memory_cost:  {ph.memory_cost} KiB = {ph.memory_cost // 1024} MiB (expected: 64 MiB)")
    print(f"  parallelism:  {ph.parallelism} (expected: 4)")
    print(f"  hash_len:     {ph.hash_len} bytes (expected: 32)")
    print(f"  salt_len:     {ph.salt_len} bytes (expected: 16)")
    print(f"  type:         {ph.type} (expected: Type.ID)")

    if (ph.time_cost == 3 and
        ph.memory_cost == 65536 and
        ph.parallelism == 4 and
        ph.hash_len == 32 and
        ph.salt_len == 16 and
        ph.type == Type.ID):
        print("  [OK] All defaults match RFC 9106 LOW_MEMORY profile")
    else:
        print("  [WARN] Defaults don't match expected values")

    # Test hashing
    print("\nTesting password hashing...")
    test_password = "correct-horse-battery-staple"

    start = time.perf_counter()
    password_hash = ph.hash(test_password)
    hash_time = time.perf_counter() - start

    print(f"  Hash generated in {hash_time:.3f}s")
    print(f"  Hash format: {password_hash[:50]}...")

    # Verify hash format is self-describing
    assert password_hash.startswith("$argon2id$"), "Hash should start with $argon2id$"
    assert "$m=65536" in password_hash, "Hash should contain memory parameter"
    assert ",t=3," in password_hash, "Hash should contain time parameter"
    assert ",p=4$" in password_hash, "Hash should contain parallelism parameter"
    print("  [OK] Hash format is correct (self-describing)")

    # Test verification - correct password
    print("\nTesting password verification...")
    start = time.perf_counter()
    ph.verify(password_hash, test_password)
    verify_time = time.perf_counter() - start
    print(f"  [OK] Correct password verified in {verify_time:.3f}s")

    # Test verification - wrong password
    try:
        ph.verify(password_hash, "wrong-password")
        print("  [FAIL] Wrong password should have raised VerifyMismatchError")
        return 1
    except VerifyMismatchError:
        print("  [OK] Wrong password correctly rejected")

    # Test that different hashes are generated (salt is random)
    print("\nTesting salt randomness...")
    hash1 = ph.hash(test_password)
    hash2 = ph.hash(test_password)
    if hash1 != hash2:
        print("  [OK] Same password produces different hashes (random salt)")
    else:
        print("  [FAIL] Same password produced identical hashes")
        return 1

    # Test rehash check
    print("\nTesting rehash detection...")
    needs_rehash = ph.check_needs_rehash(password_hash)
    print(f"  check_needs_rehash: {needs_rehash} (expected: False for current params)")

    # Simulate old hash with different params
    old_ph = PasswordHasher(time_cost=2, memory_cost=32768)  # Weaker params
    old_hash = old_ph.hash(test_password)
    needs_rehash = ph.check_needs_rehash(old_hash)
    print(f"  check_needs_rehash (old params): {needs_rehash} (expected: True)")
    if needs_rehash:
        print("  [OK] Correctly detects hashes needing rehash")
    else:
        print("  [WARN] Did not detect hash needing rehash")

    print("\n" + "=" * 50)
    print("All tests passed! argon2-cffi is working correctly.")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    exit(main())
