#!/usr/bin/env python3
"""
Utility script to generate an AES-256-GCM encryption key and JWT secret.
Run this script to generate values for your .env file.
"""
import os
import secrets

def generate_keys():
    jwt_secret = secrets.token_hex(32)
    # AES-256 key needs to be exactly 32 bytes (64 hex chars)
    aes_key = secrets.token_hex(32)
    
    print("\n?? Generated Security Keys:\n")
    print(f"SECRET_KEY={jwt_secret}")
    print(f"TOKEN_ENCRYPTION_KEY={aes_key}")
    print("\nCopy these into your .env file.\n")

if __name__ == "__main__":
    generate_keys()
