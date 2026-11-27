# Research OS Windows Code Signing

## Purpose

This policy adds Authenticode signing to the existing exact-SHA Phase E Windows distribution. It does not replace the release spine, provenance, manifest, installer E2E, or Final Gate authority.

## Authorization model

- Pull-request and ordinary candidate builds remain unsigned.
- Signing is enabled only by a manual workflow_dispatch on main, with the explicit authorize_signing=true input.
- The workflow also checks that the actor is the canonical repository owner.
- The signing job uses the protected GitHub Environment named code-signing. Configure required reviewers for that environment before using it.
- The signing job reads only the environment secrets WINDOWS_CODESIGN_CERT_BASE64 and WINDOWS_CODESIGN_CERT_PASSWORD.
- No certificate, password, PFX, or secret value belongs in the repository, workflow inputs, artifacts, or logs.

## Certificate requirements

Use a currently valid Code Signing certificate issued by a publicly trusted CA, with its private key available in PFX form. The workflow checks the Code Signing EKU, rejects a self-issued leaf certificate, signs with SHA-256, adds an RFC 3161 timestamp, and verifies each resulting signature with Windows Authenticode policy before packaging.

The PFX should contain the leaf signing certificate and required intermediate certificates. Keep the PFX and password in the protected environment only. Never use a self-signed certificate as a substitute for public distribution signing.

## Secret configuration

After the PR is reviewed and merged, an authorized repository administrator must configure the code-signing environment in GitHub Settings:

1. Add required reviewers to the environment.
2. Add WINDOWS_CODESIGN_CERT_BASE64 containing the Base64-encoded PFX bytes.
3. Add WINDOWS_CODESIGN_CERT_PASSWORD containing the PFX password.

This PR does not create, edit, or reveal any GitHub secret. The existing audit found no such secrets configured.

## Publication gate

The distribution build emits CODE_SIGNING_EVIDENCE.json. Unsigned builds explicitly record NOT_SIGNED and remain useful as CI candidates, but are not publishable.

When the Release workflow is dispatched with publish=true, it installs osslsigncode and independently verifies:
- the exact-SHA setup executable;
- every .exe payload inside the exact-SHA Platform ZIP;
- the trusted CA chain using the runner's system CA bundle;
- non-self-issued signer identity;
- agreement of signer identity across all executable payloads;
- evidence hashes, source SHA, and executable inventory counts.

Any missing, unsigned, invalid, untrusted, self-issued, or mismatched signature fails the workflow before GitHub Release creation. The Release workflow still requires its existing Final Gate, provenance, lineage, and installer evidence.

## Safety boundary

A successful build or signature check does not authorize installation on a user's machine. Runtime identity remediation, data-preserving upgrade validation, and release readiness remain separate gates. Do not install or publish until all those gates pass.
