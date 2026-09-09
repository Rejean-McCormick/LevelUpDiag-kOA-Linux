# Modular product UI diagnostics

LevelUpDiag-Koali treats modular product UI behavior as an **integration diagnostic**, not as a definition of Koali user-interface architecture.

## Authority boundary

Koali canonical documentation and each product's admitted public contract define what counts as its standalone entry point, integrated contribution, commands, routes, surfaces, inspector declarations, or other UI assets. LevelUpDiag only evaluates explicit diagnostic configuration.

It MUST NOT:

- make kOA Spaces a mandatory runtime for a product UI;
- make Konnaxion, Orgo, Kristal, or another product a mandatory UI dependency of another product;
- invent a universal product-manifest filename;
- copy product business semantics into diagnostic code;
- treat an intentionally removed optional product as a Koali core failure.

## Configuration

The optional `ui_modularity` object is read from the normal LevelUpDiag configuration merge.

```json
{
  "ui_modularity": {
    "enabled": true,
    "base_root": "..",
    "products": [
      {
        "id": "product-id",
        "root": "product-repository",
        "required": false,
        "standalone_markers": ["path/declared/by/product"],
        "integration_markers": ["path/declared/by/integration-contract"],
        "scan_files": ["package-or-source-file"],
        "forbidden_private_ui_tokens": ["private-import-token"]
      }
    ]
  }
}
```

`base_root` is resolved relative to the LevelUpDiag tool root. Product roots can be absolute or relative to that base. Marker and scan paths are product-relative and cannot escape the configured product repository.

## Verdicts

- optional product absent: `PASS` — removal is accepted;
- required product absent: `BLOCKED`;
- available product with configured markers present: `PASS`;
- configured marker missing: `FAIL`;
- configured forbidden private UI token found: `FAIL`;
- invalid paths or malformed configuration: `CONFIG_ERROR`;
- unreadable configured scan input: `INFRA_ERROR`.

A `PASS` for an absent optional product means only that the removal state is permitted. It is not positive functional evidence for that product.

## Campaign placement

The check runs from N06 Integrations. The default `stabilization` campaign remains N00/N01/N04/N05 and therefore does not depend on UI products. Broader `debug`, `validation`, and `release` selections can include N06 according to their existing policies.

## Security and boundedness

The check is read-only. It reads only explicit marker paths and explicit scan files. Each scan file is bounded to 512 KiB of text and only reports configured token/path metadata, not arbitrary source content.
